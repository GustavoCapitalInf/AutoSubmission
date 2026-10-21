# Lender detection and flagged positions: design

- **Date:** 2026-09-24
- **Branch:** `lender-detection`, from `text-first-v1` at `31f86b7`
- **Owner:** Gustavo
- **Status:** implemented as classification 5.0 to 5.4 and 5.9. Amendments are marked in place, and `docs/transaction-classification.md` states the rules as built.
- **Comes before:** the text-first reader (`2026-09-24-text-first-reader-design.md`)

## 1. Why

Across many statements, the owner kept catching lenders that detection missed. Two things were investigated:

- **A census:** today's code run read-only over the 7,241 analyses cached in the local job store, covering 675,935 debits.
- **A research ledger:** every payee that looked like a lender, identified from public sources and then independently re-checked by a second agent.

The census and the code found three kinds of failure.

**Missed lenders**
- NMEF is filed as "lease or equipment financing", which never reaches the lender list. The owner's example statement is `CHECKCARD … NMEF FUNDING`.
- Many MCA funders have no registry entry at all: Legend Advance Funding, Hunter Caroline, Zlur Funding, Coconut Funding and Lendr are among those confirmed so far.
- Spellings that run words together slip past the aliases. `FORWARDFINANCING` does not match the alias `FORWARDFINANCIN`, and `EXPANSIONCAP` matches no Expansion Capital alias.
- Some rules run before the lender check and take lender payments away:
  - a lender paid by debit card becomes a POS purchase;
  - a lender paid by check is never a lender.
- Payees hidden behind bank-channel prefixes are never matched, e.g. `BUSINESS TO BUSINESS ACH DEBIT … <funder>`.

**Wrongly counted, or wrongly shown as potential lenders**
- These are counted as lenders today, and the owner now rules they are not: SBA/EIDL, BDC, Affirm, Intuit, Square Capital, Shopify Capital, PayPal Working Capital, Fundbox, BlueVine and Kabbage.
- These are shown as potential lenders today but are other obligations: American Express, TD Auto Finance, RBC loan payments and plain "LOAN PAYMENT" rows.

**Missing obligations**
- Bank loans (for example `TRUIST LN … PYMT`), vehicle loans, mortgages and card payments are either "other" or classified inconsistently.

## 2. Owner rulings (2026-09-24)

| Group | Counts as a lender? | Who |
|---|---|---|
| **Lender** | **Yes**: lender count, lender totals, withholding | MCA and revenue-based funders (OnDeck, Bitty, Legend, LG Funding, Hunter Caroline, CAN Capital, CanaCap and so on) and **equipment financing** (NMEF, Balboa, Navitas, Deere, office-equipment captives such as Pitney Bowes and Canon Financial, heavy-truck lenders such as Daimler Truck and PACCAR, and so on) |
| **Potential lender** | No; review, as today | Unknown payees with lender signals |
| Flag: **Alternative positions** | No | SBA/EIDL, BDC, Affirm and other BNPL, Amex loans and lines, Intuit, Square, Shopify, PayPal, Stripe and Amazon financing, and Capital Infusion (the house) |
| Flag: **Lines of credit** | No; called out separately as LOC | Fundbox, BlueVine (`BLUEVINE CAPITAL`), Kabbage, and any row whose descriptor says LOC or LINE OF CREDIT |
| Flag: **Credit cards** | No | Card payments to Amex, Capital One, Chase, Credit One, Concora and so on |
| Flag: **Vehicle loans & leases** | No | GM Financial, Ford Credit, Toyota Financial, Ally, auto leases |
| Flag: **Bank loans** | No | A bank's own loan payments, e.g. `TRUIST LN … PYMT` |
| Flag: **Mortgages** | No | Mortgage servicers |
| Flag: **Leases & rentals** | No | Equipment rentals, leases, card-terminal (POS equipment) lessors such as LADCO Leasing and First Data Global Leasing, lease-to-own (Progressive, SmartPay Leasing, Snap) |
| Flag: **Personal loans** | No | Consumer and student loans paid from the account |
| Flag: **Floor plan** | No; flagged like alternative positions | Inventory (floor-plan) lenders for dealers: NextGear Capital, Westlake Flooring… |
| Flag: **Factoring** | No; flagged like alternative positions. Their payouts to the business stay revenue and are flagged too (owner, 2026-09-26) | Invoice factoring companies: RTS Financial, OTR Capital, Apex Capital, BC Factoring… |
| Flag: **Premium financing** | No; the rows **stay counted as insurance** as today, and are also flagged | Insurance premium financing: IPFS, First Insurance Funding (including rows that print only `FIRST INSURANCE`)… |
| Flag: **Debt relief** | No; flagged, never lender math | Debt-settlement dedicated-account processors (RAM Payment / Reliant, Global Holdings, Forth, CFTPay), debtor-side debt-relief firms and law firms (Tayne Law Group, Delancey Street, Rise Alliance), credit-counselling debt-management plans |

*Amendment (owner, 2026-10-11; classification 5.9, `ANALYSIS_STAGE_VERSION` 38):* **Amerifi Capital (Amerifi Capital, LLC) is a counted lender** ("amerifi is a lender we count"), a direct merchant cash advance funder; its daily debits printed `Electronic Withdrawal To AMERIFI CAPITAL` read as a potential lender (D6) until the ruling. The ledger admits it with the one alias `AMERIFI CAPITAL` (verify round r9), so its debits are paid to lenders, in the withholding rate and in the lender count, while a row whose own words say LOC or LINE OF CREDIT goes to Lines of credit (D9), and its credits are financing proceeds (D1). Bare `AMERIFI` (a broker's name) and the cut `AMERIFI CAP` (another registered company's name) are never aliases, and names that only start the same (AMERIFIRST, AMERIFIELD, AMERIFINANCIAL, AMERIFIX, AMERIFY, AMERIFACTORS) are other words. No cached corpus row prints the name.

*Amendment (owner, 2026-09-28; classification 5.4, `ANALYSIS_STAGE_VERSION` 23):* **Idea Financial (Idea 247, Inc.) is a counted lender**, an online business term lender, no longer a line of credit; this reverses the 2026-09-25 filing below, and its printed ACH spellings `IDEALOAN` and `IDEA 247 INC` were admitted on this ruling, while a row whose own words say LOC or LINE OF CREDIT still goes to Lines of credit (D9) and its credits stay financing proceeds (D1).

*Amendment (owner, 2026-09-27; classification 5.3):* The owner read the false-potential-lender hunt of 2026-09-27 and ruled three things. The implementation plan is `docs/superpowers/plans/2026-09-27-false-potential-lenders.md`.
- **One release in three parts** (classification 5.3, `ANALYSIS_STAGE_VERSION` 22):
  - (A) D6-only skips, where the rows stay `other` (§3 D6);
  - (B) extensions of existing rules that change a row's state: fee and NSF, cheque, card payment, the Amex loans printed in the bank's field order, payroll and benefits, mortgage `MTG` wording, and POS labels where right (§4.3);
  - (C) the registry, naming and the tab: review entities of the vehicle, mortgage, personal-loan and lease groups go to their flag, marked unconfirmed, with the credit side unchanged (§5); ledger renames and the missing funders; the glued-digit matcher gap (§4.6); the naming fixes, which are Truist's `ACH CORP DEBIT`, the CO cue, the legal-form position, wires' beneficiaries and the D10 label (§3 D10, D11); and one Potential Lenders line per unnamed payee key (§4.5).

  Lender math moves in three places only: the new funders, the glued-digit matcher (GOAT ADVANCE), and the Amex loans read in the bank's field order, which become an alternative position instead of a potential lender.
- **A twelfth flag group, Debt relief.** It has a Settings checkbox, default on, never enters lender math, and is shown like the other flags. It covers debt-settlement dedicated-account processors and debtor-side debt-relief firms: RAM Payments / Reliant, Global Holdings (`GHLLC`), Tayne Law Group, Resolve Capital, and well-known debt-relief brands printed by name (§5).
  - Resolve Capital stays under review, because no source ties the printed originator to the negotiator. Its debits take the flag, marked unconfirmed (§5).
  - The orchestrator decided three more points on 2026-09-28, delegated by the owner. There is no bare `FORTH` alias. There is no card form `DELANCEY STREET NEW YORK`. A debt-relief payee's credits (the debtor's own escrow refunds) keep today's treatment.
- **The missing funders**, after a research check:
  - Flexibility Capital, Merit Business Funding and Essentia Funding count as lenders.
  - National Funding gains its `NFSPV<d>COLLECTION` spelling.
  - GOAT ADVANCE's debits, which print digits glued to the alias, are read through the matcher (§4.6).
  - Merit Business Funding is admitted with its full name only. Its short spelling `MERIT BUSINESS` is a separate review entity: its rows are named on the Potential Lenders tab and never counted (orchestrator's decision of 2026-09-28, delegated by the owner).
  - Samson Servicing is a review alias only, because no source ties it to a funder.

*Amendment (owner, 2026-09-26):* The owner answered three questions himself.
- **Factoring payouts are revenue, and still flagged.** A credit from a factoring payee (RTS Financial, OTR Capital, Apex Capital, BC Factoring and the ledger's other factoring entities) is the business's own sales, paid by the factor that bought its invoices. It is **not** financing proceeds.
  - It keeps a payout credit's treatment (D1's exception): the operating-revenue path, never subtracted from eligible deposits.
  - It also carries the Factoring flag, the way a premium-financing row stays insurance and is flagged.
  - Factoring debits are unchanged.
  - This reverses D1 for factoring only: floor plan, lines of credit and the other financing groups keep D1 (§3, §4.2, §4.4).
  - Measured before the ruling: 1,174 factoring credits in 157 cached accounts. The ruling returns them to eligible deposits.
- **Re-analysis reads only the saved reading.** S5's Decision 2 is ratified. A statement whose reading is not cached is refused (`READING_NOT_CACHED`), and the owner accepts the decision's two known limits (§8.6).
- **Reviews a rule now decides are reported apart.** S5's Decision 5 is ratified. The re-analysis reports them as `reviews_decided_by_rules`, not as reviews that need redoing (§8.6).

*Amendment (owner, 2026-09-25, delegated to the orchestrator):* The owner read the counted lender list and delegated every open question to the orchestrator ("take your suggestions"). The orchestrator's decisions are now owner rulings. The curated ledger records each one in the entity's notes, and the evidence ledger shows it.
- **Capital Infusion (the house) is not a lender, but it is flagged.** It is admitted under Alternative positions on the owner's ruling.
- **Everest Business Funding and EBF Holdings are one funder**, so they count once. EBF Holdings' spellings are aliases of Everest Business Funding (§5).
- **Card-terminal (POS equipment) lessors are Leases & rentals, not lenders:** LADCO Leasing, First Data Global Leasing, LogicaLease and Finova Capital's point-of-sale lease product. Office-equipment captives (Pitney Bowes' leasing arms, Canon Financial) and heavy-truck lenders (Daimler Truck, PACCAR, Volvo, Mack) stay lenders, as equipment financing; Pitney Bowes' postage credit lines (Purchase Power, PitneyWorks) stay Lines of credit.
- **BlueVine is `BLUEVINE CAPITAL` and `BLUEVINE LOAN`.** The bare alias `BLUEVINE` is dropped (§5).
- **SmartPay is SmartPay Leasing**, the lease-to-own company. The `SMARTPAY SOL` rows are SmartPay Solutions' insurance premium billing, and they stay unflagged (§5).
- **Bare `FIRST INSURANCE` is FIRST Insurance Funding.** Those rows stay insurance and are also flagged premium financing (§4.2, §5).
- **Payout credits are revenue.** Credits from Sezzle, American First Finance and Payability are the account holder's own sales, settled by the platform (D1).
- **Unnamed loan payments are bank loans** of the statement's bank, not potential lenders (D5).
- **Filings confirmed:**
  - counted lenders: Econolease (equipment finance), CMCA Finance, Lily Advance, Loot Financial Services, and Payability for its debits;
  - Floor plan: AFC Funding Corp;
  - as filed: Amazon Capital Services and American Express Loans (Alternative positions), Kabbage and IDEA Financial (Lines of credit; IDEA Financial counts as a lender since the owner's ruling of 2026-09-28, above), LoanMe (Personal loans);
  - review, never counted: Clover Equipment (every spelling carries lease or rental wording, so step 8 flags its rows under Leases & rentals before the review tier is read), Rewards Network, and MERCH PAD (probably Merchant Growth; no public source ties the name to it);
  - not flagged: Keep Technologies (`KEEP BUS`; D6 still sends fixed daily or weekly debits to review), PayPal's generic debits, and PetroCard;
  - rejected: MR BIZ CAPITAL, a broker, not a funder the account pays.
- **Descriptor rules.** Where a decision needed a rule rather than an alias, S2 carries it in the §4.3 order:
  - step 4: a row with premium-finance wording and no named financier is insurance, flagged premium financing;
  - steps 5 and 7: Klarna's paid membership and balance top-ups are not BNPL repayments, so they match no known payee;
  - step 6: `OVERDRAFT CHARGE` is a fee, so the bank's overdraft charge for a Zip item is not a Zip payment;
  - step 8: a transfer between the holder's own accounts is not an obligation, even when the holder named the account with loan words; a per-vehicle floor-plan payoff is Floor plan; a home-equity loan is a mortgage; an unnamed student loan is a personal loan; the statement bank's own loan wording (in English or French), another bank's unnamed commercial loan and commercial-loan billing are bank loans; the card-payment wording is widened;
  - step 11: `MCA SERVICING` is an unknown servicer (D10);
  - credits: a per-vehicle floor-plan advance, the statement bank's own `LOAN CREDIT` and a line-of-credit draw are financing proceeds (D1).

*Amendment (owner, 2026-09-25, after research round 5):*
- **Online business term lenders count as lenders.** This covers OnDeck's term loans, National Funding, Expansion Capital, iCapital, ARF Financial and similar, the same as MCA funders.
- **Short-term rentals are flagged under Leases & rentals** (U-Haul, Sunbelt, United Rentals, Herc).
- **The numbered Ontario company** debited daily/weekly is a **potential lender** for review, through the D6 recurrence rule. It gets no alias, and its number is never written anywhere.

*Amendment (owner, 2026-09-24):* Floor plan, Factoring and Premium financing were added after round 2 of the research. Each has its own checkbox, default on. The floor-plan and factoring rows are flagged like alternative positions. Premium-financing rows keep the `insurance` state and their insurance totals, and also carry the flag.

- Every flag group has its own Settings checkbox.
- Every checkbox is **on by default**.
- Unticking a checkbox persists, and it applies to every statement, old and new, without re-analysis.
- Flag groups never enter lender math.

## 3. Decisions this spec makes (the owner may overrule any of them at review)

The code forced these choices, and the rulings above did not settle them.

- **D1. Financing proceeds.** A credit from any financing group is financing proceeds. That covers lenders, alternative positions, lines of credit, bank loans, vehicle financing, mortgages and personal loans. Proceeds are `non_revenue` and are subtracted from eligible deposits. This is today's treatment for everything in the lender registry, so the withholding denominators for SBA, Intuit and LOC proceeds do not move. The card-issuer and lease/rental lists never apply to credits: an Amex merchant settlement is revenue.
  - **Payout credits (owner, 2026-09-25).** A credit from Sezzle, American First Finance or Payability is the account holder's own sales, settled by the platform (BNPL merchant payouts, early marketplace payouts). It is revenue, not financing proceeds, and keeps today's treatment of platform settlements. The registry names these entities in `PAYOUT_CREDIT_ENTITIES`. Their debits keep their group: Sezzle and American First Finance are alternative positions, and Payability stays a counted lender. Today Payability's credits are lender credits, so revenue rises where it pays out. Only these three are excepted; Affirm stays under D2.
  - **Factoring payouts (owner, 2026-09-26).** A credit from a factoring payee is the business's own sales, paid by the factor that bought its invoices. It is revenue, as a payout credit is, and it is never subtracted from eligible deposits. Unlike a payout credit, the row also carries the Factoring flag: it is recorded as `factoring` under its payee (§4.2, §4.4). Factoring debits keep their group. The exception covers the whole factoring group, and no other group.
- **D2. Affirm credits** keep today's treatment as financing proceeds. Whether an Affirm merchant payout is revenue is a separate revenue question and is out of scope here.
- **D3. Plain rent is not flagged.** Landlord and office rent stay `rent`. "Leases & rentals" covers equipment rentals, leases and lease-to-own.
- **D4. Unnamed equipment financing.** A generic `EQUIPMENT FINANCING/FINANCE` descriptor with no named company is a **potential lender** (review), never a counted lender.
- **D5. Unnamed loan payments** (amended by the owner, 2026-09-25). A loan payment that prints no lender is the statement bank's own loan, so it is a **bank loan**, not a potential lender. The row's entity is the statement bank when it is known. A loan payment is a bank loan when:
  - the payee is on the bank-name list, with loan wording;
  - the descriptor is the statement bank's own loan transfer (e.g. `TRANSFER TO LOAN …`) or its own loan wording;
  - it carries loan-payment wording (`LOAN PAYMENT`, `LOAN PYMT` and the like) and prints no payee at all: no lender, servicer, person or other bank.

  A loan payment that prints any other payee keeps today's rules: a known payee, the bank-name rule, or the potential-lender rules.
- **D6. Unknown MCA-style debits.** A payee on no list, with debits of the **same amount** on **at least three different dates** on a **daily or weekly** cadence, becomes a **potential lender** (review). Several debits on one date count as one. This does not apply to rows that are already a POS purchase, transfer, fee, payroll, tax, utility, rent or insurance, nor to card-purchase postings that the POS rule does not read (clarified 2026-09-26):
  - a posting that starts `PURCHASE` and its mmdd, after an optional `RECURRING`;
  - a descriptor with a `processor*merchant` mark (`TST*NAME`, `SQ *NAME`, `TST* NAME`): a letter or digit, an optional space, `*`, an optional space, a letter or digit. It is read only on a row that carries no ACH field mark (`ACH`, `CCD`, `PPD`, `CTX`, `WEB`, `DES:`, `INDN`, `CO ID`, `ID:`, `ORIG CO`, `RMR`), because an ACH entry prints stars too: in its addenda (`RMR*IV*`), a masked account or an ID.

  The word `PURCHASE` alone is not a card mark: an ACH entry description can print it. D6 relaxes "recurrence alone is never lender evidence" for the **review tier only**. Nothing is ever *counted* without a named lender.

  Clarified 2026-09-27:
  - D6 does not take a row whose words name compensation: a commission (with its misspellings, such as `COMMISION` or `COMISSION`), a bonus, a salary, a stipend or a reimbursement. Pay is not an MCA remittance. The row stays `other`.
  - A masked recipient account printed after `TO` (`To ....1234`, `TO XXXX1234`, `TO ***1234`, `TO #1234`) is part of the payee. Payments to different recipient accounts are never one payee.

  Clarified 2026-09-27, classification 5.3 (the false-potential-lender release). D6 does not take these rows either; they stay `other`, and their groups leave the recurring-debit view too:
  - **Channel words.** A payee whose words are all bank channel words (a card, cash, cheque or bill-pay posting printed without its merchant or recipient, such as `BILL`, `RECURRING`, `AUTOPAY`, `MISCELLANEOUS`, `ATM`, `TELLER`, `CHK`) names no payee. The rule does not fire when the payee region prints an organisation cue, so a format that prints a reference before the merchant stays in review. `OTHER`, `BANK` and the bare withdrawal abbreviations (`WD`, `WDL`, `WDRL`) are left out on purpose: 'Other Debit', 'Bank Debit' and 'Preauthorized Wd' rows stay in review.
  - **Card formats the POS rule does not read.** These are read on the whole row, never on one that names financing, a bank, an investment firm or an organisation (an organisation cue, or a word such as `HOLDINGS`, `PARTNERS`, `GROUP`, `SOLUTIONS`), because funders are paid by debit card in these formats too.
    - The card labels: Bank of America's merchant-first `mm dd <ref> PURCHASE` row, `DBT CRD` / `DEBIT CRD`, a leading `DEBIT CARD`, a type-only `CARD` row, Square's 'Card spend', Wells Fargo's '… authorized on mm/dd … Card nnnn', `PIN DEBIT`, `RECURRING (DEBIT) CARD`, `CARD TRANSACTION`, `PURCH`, `CARD ENDING IN` and `DDA PUR`.
    - A Wealthsimple Chequing row that prints none of its other channel words: Wealthsimple prints a card purchase as the bare merchant. Its bill-payment print form is unverified.
    - The card network's merchant location, 'NAME, CITY, ST' (Bluevine) or 'NAME ###, CITY , ST , USA' (Lead Bank / Found), on those two banks' rows only and only without an ACH field mark. Bluevine's glued 'CITY, NYUS' variant is a known non-match.
    - Wells Fargo's 'Recurring Payment authorized on … Card nnnn' is skipped on its format, as 'Purchase authorized on' is, even when it pays a person with a website. The owner is told.
    - A card purchase printed as the merchant's name alone, with no card label, stays in review. This brand-only residual is accepted policy.
  - **Person-to-person, wallet and card-push rails** (`VIREMENT`, `ZEL TO` / `ZEL FROM`, `PMNT SENT` / `PAYMENT SENT` with its mmdd, `APPLE CASH`, `APPLE WALLET`, `WISE INC`, `WISE US INC`, `TRANSFERWISE`, `DES WISE`, `IAT PAYPAL`, `GREENLIGHT DES APP`). They are read before the receiver fields. `VIREMENT` covers every French RBC transfer line (Interac e-Transfer, 'Virement envoye', 'Virement par Banque en direct'). Bare `WISE` is never a rail (WISE CHOICE, FINWISE). These rails stay out of the transfer rule, which runs before the known payee and would hide a counted funder paid by e-Transfer.
  - **Transfer templates**, only for a payee that names no organisation (D11 would publish 'Unidentified lender obligation'). The templates are:
    - the abbreviations `XFR`, `TRF`, `TRSFR` and `TRNSFR`, and `TRANSFER`, `XFER` or `TFR` with digits glued on;
    - 'TO <account type> <number>' (`CHKG`, `CHK`, `CHECKG`, `CHECKING`, `SAV`, `SAVINGS`, `SVGS`, `SHARE`, `SHARES`, `MMA`). This one is recorded for the owner, who may strike it: a banking-centre 'TO CHKG <n>' names no counterparty;
    - a bare internet, online, phone, mobile or web withdrawal;
    - Atlas's Smart Save sweep (`SMARTSAVE`, then only reference numbers, then `ATLASFINANCIAL` or `ATLASFIN`, run together or spaced);
    - `RTP SENT`, `REAL TIME PAYMENT TO` and `FEDNOW PAYMENT TO`.

    Today's `TRANSFER` / `XFER` / `TFR` skip is unchanged and needs no such condition.
  - **Cash, own-batch offsets, tuition and childcare**, read before the receiver fields:
    - the holder's cash withdrawal in the formats the ATM rule does not read. Only reference tokens or `NETWORK` may sit between `ATM` / `ABM` and the withdrawal word, so a payee name never fills the gap. The same goes for `WITHDRWL`, a `CASH WITHDRAWAL` after a teller, counter, branch or ATM word, and the French `RETRAIT` forms;
    - the offset of an ACH batch the holder sent from its own bank's portal (`BUS ONLINE ACH SETTLEMENT`, `ACH SETTLMT REL DATE FUND`);
    - FACTS tuition billing, and tuition, daycare, childcare, preschool and Montessori billing (with KinderCare, brightwheel and Procare).
  - **Savings and investing apps**, a closed list of verified non-funder ACH names: Stash, Alinea, Fidelity Brokerage Services' MoneyLine (`FID BKG SVC`), Albert's `EDI PYMNTS`, Acorns, Robinhood, Coinbase, Betterment and Wealthfront. Bare `VANGUARD`, `INVEST`, `SAVINGS`, `FIDELITY` and `MONEYLINE` stay out.
  - **Vendors and other named non-lenders.** They are read on the D11 payee words. On a bounded row only (an ACH field, or a reference after the name, ends the payee's words), the originator segment is read as well. A receiver field is never read, and neither is the holder's name. The vocabulary, verbatim:
    - `BOOKK…`, `DISTR`, `DISTRIBUT…`, `FOODSERVICE`, `MANUFACTURING`, `INVOICE`, `INVOICES`;
    - `CINTAS…`, `UNIFIRST`, `ARAMARK`, `SYSCO`, `ALSCO`, `US FOODS`;
    - as the payee's first words: `FACEBOOK`, `FACEBK`, `META ADS`, `META PLATFORMS`, `GOOGLE ADS`, `TIKTOK ADS`, `YELP`, `ANGI`, `HOMEADVISOR`, `THUMBTACK`;
    - `UNIFORM`, `UNIFORMS`, `LINEN`, `JANITORIAL`, `LANDSCAP…`, `LAWN`, `PEST CONTROL`;
    - `ROYALTY`, `ROYALTIES`, `FRANCHIS…`, `AD FUND`, `MARKETING FUND`, `ADVERTISING FUND`;
    - `TITHE…`, `CHURCH`, `MINISTRIES`, `DONATION`, `DONATIONS`, `PUSHPAY`, `GIVELIFY`, `VANCO`, `SUBSPLASH`, `EASYTITHE`;
    - `EZPASS`, `ZPASS`, `SUNPASS`, `FASTRAK`, `TXTAG`, `NTTA`, `HCTRA`, `PEACH PASS`, `IPASS`, `BESTPASS`, `PREPASS`, `TOLL`, `TOLLS`, `TOLLWAY`;
    - `DRAFTKINGS`, `FANDUEL`, `BETMGM`, `LOTTERY`, `OLG`, `CASINO`;
    - a Bill.com or Melio payment, only when the row prints an invoice number (`INV <digit>`).

    The skip never fires when the rest of the row prints a lending word (the shared roots below, plus the Canadian pre-authorized-debit word `PAD`), or when the payee words carry one of the holder's own name words. A vendor word run together with a lending root (`…DISTRIBUTIONCAPITAL`, `BOOKKEEPINGFUNDING`, `…DISTRIBUTORSCREDIT`) is no vendor word; the whole word `FUND` of the ad-fund phrases is their own vocabulary. On a row that is one run of words and whose holder's name is unknown, the vendor word must be the payee's first word. The recorded residual is a label-less row that prints the receiver before a reference. `DISTRIBUT…` also clears recurring owner distributions.
  - **Tax and government payees** printed without `TAX`, `IRS` or `CRA`: the U.S. Treasury, `EFTPS`, `CCRA`, the Receiver General, a Secretary of State, a state SOS or DMV, a motor-vehicles department, `DTF`, `EDD`, `DOR`, `TAXATION`, `COMPTROLLER`, a revenue department, a state treasurer or treasury, Revenu Québec, and the workplace-insurance boards (`WSIB`, `WORKSAFE…`, `WCB`, `EHT`, `CNESST`). They are read on the payee region only (never an entry description or memo), and only for a payee that names no organisation. The tax rule itself is not widened: it runs before the known payee and has no amount guard. The financing-keyword recurrence never promotes a government finance department (`DEPARTMENT OF FINANCE`, `FINANCE DEPT` and the like) or a retailer named ADVANCE (`ADVANCE AUTO PARTS`, `ADVANCE STORES`). Their single rows stay `other` / `financing_keyword_review`.
  - **Family support**, in both recurrences: `CHILD SUPPORT` and its abbreviations, a family-support registry or payment center, and a `STATE DISBURSEMENT UNIT`. This is read before the receiver fields. `GARNISH`, `LEVY`, `LEGAL ORDER`, bare `SDU` and `CSE` stay in review: an MCA judgment creditor collects through a law office or a marshal.
  - **Owner pay and platform payouts to a person.** An owner's, member's, partner's or shareholder's draw or distribution, a dividend, a per diem or a guaranteed payment is owner money. It is read before the receiver fields, with the veto (`DIVIDEND FINANCE` is a lender); a bare `DISTRIBUTION` is a vendor's name. A payments platform's 'Pay To: <recipient>' payout (Payoneer) is skipped only when the recipient is a person: an organisation, the platform itself or no recipient stays in review, because Payoneer's Capital Advance is collected by ACH debit.
  - **The $25 floor for unnamed payees.** D6 does not take a same-amount group under $25 whose payee names no organisation (it would publish as 'Unidentified lender obligation') and whose row names no financing. The comparison is strict: a $25.00 group still promotes. A named payee promotes at any amount. These groups also leave `detect.find_recurring_debits`, so they leave the CLI's 'Recurring fixed debits' lines, `batch.py`'s `recurring_debit_groups` and `detection.recurring_debits` too.
  - **A processor's own charge of $50 or less**, through its merchant-services spelling: Square's seller-account entry code (`SQUARE` with `SQ` and the entry date) and Intuit Payment Solutions. It never applies with loan or capital wording, Square's glued loan codes (`SQCAP`, `SQ LOAN`) included. A fixed debit above $50 on these rails stays in review, because they also carry invoice payments to third parties.
  - **Truncated insurers**: an insurer whose name the ACH field cut short (`INSU`, `INSUR`, `INSURA`, `INSURAN`, `INSURANC`), read on the D11 payee words only. `INSURED`, `INSURER` and the bare `INS` stay out.
  - **Phone and cable carriers**, matched at the start of the payee's leading words (after bill-payment prefix words), so a carrier printed after the payee's own name never decides. Brand names only (Koodo, Fido, Telus, Videotron, T-Mobile, Verizon, Comcast, Xfinity and the like). `BELL`, `ROGERS`, `SHAW` and `SPRINT` need their telecom word, and `ATT` counts only in its bill and payment forms. The `VERIZON` exception covers the registry's Verizon Visa alias only.
  - **A listed card issuer printed alone** (§5, `card_issuer_context`): the issuer alias's words lead the payee's words, and the rest of the row names no financing.

  Every 5.3 skip reads the payee's words, never a receiver field, and every one reads the shared veto on the whole row, so none fires on a row that names financing (prefix-tolerant roots, so KOVOCREDIT, CAPITA and FUNDIN veto too, and so do SETTLE, CRED before IT, ORA, IBLY or a word end, and ACCEPT). The veto leaves out only the skip's own matched words, and those hide no name: a vendor word run together with a lending root is no vendor word, and only reference numbers may sit inside the Atlas sweep's match. The processor-charge skip also keeps its own loan and capital guard. The financing-keyword recurrence's exceptions (a government finance department, a retailer named ADVANCE, family support) carry no veto, because their rows name financing by definition.
- **D7. Unticking a checkbox only hides the flag.**
  - A setting never moves a row into review or into lender math.
  - Flag groups never change the package decision.
- **D8. Card-paid lenders.** A known lender or financing payee paid by debit card is classified by who was paid, not as a POS purchase (the NMEF example). Fees and transfers keep their precedence: `ONDECK TRANSFER FEE` stays a fee.
- **D9. LOC wins.** A descriptor that says LOC or LINE OF CREDIT puts the row in Lines of credit, even when the payee is a lender.
- **D10. Servicers.**
  - A servicer or collector whose funder is known is recorded under that funder.
  - An unknown servicer or collector is a potential lender (review).
  - An MCA SERVICING payee carries the fixed name 'MCA servicer (funder not identified)' (5.3): the words print for two unrelated funders.
- **D11. No personal names as lender names.** An unknown payee's entity name is never built from ID/INDN/IND NAME/CO ID/TRACE segments. If no organisation name is left, the entity is "Unidentified lender obligation".
  - The 5.3 naming rules (2026-09-27):
    - A legal form (`LLC`, `INC`, `CORP`, `CORPORATION`, `COMPANY`, `INCORPORATED`, `LTD`, `LIMITED`, `LP`, `LLP`, `PLLC`) counts as an organisation cue only after the name's first word.
    - A name made only of cue words names no organisation, and neither does `CO`, which is no longer a cue: it is also Colorado's state code in 'NAME, CITY, CO'.
    - The name ends at its first legal form after the first word.
    - Trailing connectors (`OF`, `AND`, `THE`, `DE`, `DU`, `DES`), `PAID` and a leading `AND` are dropped.
    - Bank template prefixes printed before the payee (`PMNT SENT`, `PAYMENT SENT`, `CORPORATE ACH`, `DOMESTIC ASSIST WIRE`, `HIP CREDIT SENT`, `RETAIL PURCHASE`, the `DBCRD PUR AP` card forms and Truist's `ACH CORP DEBIT` / `ACH CORP CREDIT`) are removed. Two recipients paid through one template are never one payee, and a template is never a name.
    - A Truist `ACH CORP DEBIT` name is published only when a whole legal-form word lies inside its 16-character company field. Truist prints no padding, so a short originator lets the receiver's words into that field.
    - A wire is named by its beneficiary: the words after `BNF` (Wells Fargo `/Bnf=`, Bank of America `BNF:`), or after the account label of Chase's 'Wire Transfer Via: <bank> A/C: <beneficiary>'. The name ends at its first organisation cue after its first word.
    - New field segments end the payee's words: Truist's receiver label `CUSTOMER ID`, Huntington's instruction field `INSTR`, and the wire fields `SRF`, `RFB` and `IMAD`.
    - A card network's 'NAME, CITY, ST' line (with no ACH field mark) is named by the printed name before the first comma alone; the city never joins the name.
- **D12. Saved jobs.**
  - Statements analysed before this change keep their stored labels until re-analysed. Nothing re-labels them silently.
  - The results page shows a notice and a **Re-analyze** action (§8.6).
  - The same holds whenever the classifier moves on: an analysis whose records carry no `classification_version`, or one older than the running version, gets the notice. A 5.0 analysis gets it once 5.1 runs (clarified 2026-09-26).

## 4. Classification model

### 4.1 States

`ClassificationState` and `CLASSIFICATION_STATES` (`analysis/transaction_classifier.py`) gain:
- `alternative_position`
- `line_of_credit`
- `vehicle_financing`
- `bank_loan`
- `mortgage`
- `lease_or_rental`
- `personal_loan`
- `floor_plan_financing`
- `factoring`
- `debt_relief` (5.3, owner ruling 2026-09-27: the Debt relief group)

`credit_card_payment` stays; it is the credit-card group.

`lease_or_equipment_financing` is retired:
- equipment financing becomes `confirmed_lender`;
- the rest becomes `lease_or_rental` or `vehicle_financing`.

The dashboard keeps a label for the retired state so that analyses stored before this change still render.

### 4.2 New fields on each classification record

- **`flagged_group: str | None`** holds the group key from the table below, or None. It is set whenever the state is one of the flag groups.
- **`contributes_to_flagged_totals: bool`** is True for a posted debit of a flag group, and for a posted factoring credit (owner, 2026-09-26: a factor's payout, which stays revenue). No other group's credit sets it. It follows the same rules as the lender flags:
  - it is off for proven duplicates;
  - it is off for settlement-reversed debits, and for a credit that the reversal pass pairs with a debit.
- **`potential_payee_label: str | None`** (5.3, 2026-09-27) is the Potential Lenders line of an unnamed potential payee: a row whose entity is 'Unidentified lender obligation' or 'MCA servicer (funder not identified)'. The rows of one payee key (entity, rule, D6 payee words, amount and masked recipient) share it within the statement. It names the entity, a recurrence's cadence and the amount, never a payee word (D11): 'Unidentified lender obligation (weekly, 450.00)'. A second key with the same label gets ' #2'. It is None on every other row, whose line is its `canonical_entity`, and `canonical_entity` does not change (§4.5).
- *Amendment (owner request 2026-10-06, R2-OW18):* **`potential_payee_key: str | None`**, directly after `potential_payee_label`, is set on every `potential_lender` row, named or not: an amount-free digest of the payee key (the entity, the D6 payee words and the masked recipient), so no payee word is published. Only `analysis.lender_payment_changes` reads it, to follow a potential lender's payee across an amount change (true revenue spec §9.1).

| State | `flagged_group` | Settings key (default `true`) | Label |
|---|---|---|---|
| `alternative_position` | `alternative_positions` | `flag_alternative_positions` | Alternative positions |
| `line_of_credit` | `lines_of_credit` | `flag_lines_of_credit` | Lines of credit |
| `credit_card_payment` | `credit_cards` | `flag_credit_cards` | Credit cards |
| `vehicle_financing` | `vehicle_financing` | `flag_vehicle_financing` | Vehicle loans & leases |
| `bank_loan` | `bank_loans` | `flag_bank_loans` | Bank loans |
| `mortgage` | `mortgages` | `flag_mortgages` | Mortgages |
| `lease_or_rental` | `leases_rentals` | `flag_leases_rentals` | Leases & rentals |
| `personal_loan` | `personal_loans` | `flag_personal_loans` | Personal loans |
| `floor_plan_financing` | `floor_plan` | `flag_floor_plan` | Floor plan |
| `factoring` | `factoring` | `flag_factoring` | Factoring |
| `insurance` (premium-finance payees only) | `premium_financing` | `flag_premium_financing` | Premium financing |
| `debt_relief` (5.3) | `debt_relief` | `flag_debt_relief` | Debt relief |

**Premium financing** is the one group that is not a state of its own. The row keeps `classification="insurance"` and `contributes_to_insurance_totals`. When the insurance match is a premium-finance payee (`PREMIUM_FINANCE_ALIASES`), the classifier also sets `flagged_group="premium_financing"` and `contributes_to_flagged_totals`. The insurance rule reads the premium-finance table before the insurer table, so a row that prints only `FIRST INSURANCE` is FIRST Insurance Funding (owner, 2026-09-25): it stays insurance and is also flagged. A row with premium-finance wording (`PREM FIN`, `PREMIUM FINANCE`, `INSPREMFIN`) and no premium-finance payee is flagged the same way, under the insurer it names, or else `Insurance provider not identified` (owner, 2026-09-25). **D1** (financing proceeds) covers `floor_plan_financing` credits. A factoring payee's credit is not proceeds (owner, 2026-09-26). It is revenue, recorded as `factoring` under its payee, with `flagged_group="factoring"` and `contributes_to_flagged_totals`: the credit counterpart of the premium-financing row, which stays what it is and is also flagged. A premium-finance payee's credits keep today's insurance treatment. Amendment (true revenue audit fix batch B6, I24, 2026-10-01): on a credit, the premium-finance lookup also reads a one-word alias of four letters or more with a digit run glued after it (`IPFS888`, `IPFSFLP12`: `registry_match(..., glued_digits=True)`), so every spelling of a premium financier's credit takes that one treatment; a debit's lookup is unchanged.

`CLASSIFICATION_VERSION` becomes `"5.0"`, `"5.1"` with the D6 clarification of 2026-09-26, `"5.2"` with the second one of 2026-09-27, `"5.3"` with the false-potential release of 2026-09-27, `"5.4"` with the owner's Idea Financial ruling of 2026-09-28, and `"5.9"` with the owner's Amerifi Capital ruling of 2026-10-11 (5.5 to 5.8 are the true revenue spec's, its §9.3).

**Debt relief** (5.3) is flagged on debits only. Its payees' credits are the debtor's own money back from the escrow, never financing proceeds: the state is not in `FINANCING_STATES`, and a credit keeps today's rules.

### 4.3 Rule order (debits). The first match wins.

1. Not posted → `other` (unchanged).
2. NSF or returned item → `nsf_or_return` (unchanged).
3. Refund, reversal or void → `refund_or_reversal` (unchanged).
4. Insurance, by registry or by term (unchanged). Premium finance stays insurance.
5. POS and ATM (unchanged), **except** when the row matches the **known-payee matcher** (§4.6). Today only the lease registry is excepted (D8).
6. Fee, then transfer, then tax, then payroll, then utility (unchanged).
7. **Known-payee matcher** (§4.6), which gives the payee's group. The one exception is LOC wording (D9): if the descriptor says LOC or LINE OF CREDIT and the group is `confirmed_lender`, `alternative_position` or `line_of_credit`, the row becomes `line_of_credit`.
8. Descriptor patterns for rows with no named payee:
   - LOC/LINE OF CREDIT → `line_of_credit`
   - MORTGAGE → `mortgage`
   - AUTO/VEHICLE LOAN, LEASE or PAYMENT → `vehicle_financing`
   - a bank name plus LOAN, LN or LOAN PAYMENT, the statement bank's own loan transfer, or a loan payment that prints no payee → `bank_loan` (D5)
   - LEASE, RENTAL or LEASE-TO-OWN → `lease_or_rental`
   - credit-card payment patterns, widened to the card issuers the research found → `credit_card_payment`
   - EQUIPMENT FINANCING/FINANCE with no named company → `potential_lender` (D4)
9. Rent → `rent` (unchanged, D3).
10. Check, then subscription → `other` (unchanged).
11. Potential-lender rules: the potential registry, direct-debit loans, explicit repayments, and financing words with a payment marker. These are unchanged, except that entity naming follows D11.

The amendment of 2026-09-25 (§2, "Descriptor rules") adds rules at steps 4, 5, 6, 7, 8 and 11 and for credits. S2's plan places each one in this order.

The 5.3 release (2026-09-27, §2) adds these rules, in the same order:
- **Step 2:** the returned-item wording `RTN STOP PAY` / `RETURNED STOP PAY` (a stop-payment return of the business's own debit) and the French `EFFETS RETOURNES`. **Step 3:** a `DEPOSITED ITEM RETURNED` is a reversal, as `RETURNED DEPOSIT` is.
- **Step 5:** more POS labels: `RETAIL PURCHASE`, `MOBILE PURCHASE` and `PIN PURCHASE`, and the French card forms `C/ACHAT`, `ACHAT AU DETAIL`, `ACHAT INTERAC`, `ACHAT PAR CARTE` and `ACHAT EN LIGNE`. A bare `ACHAT` is never read, because 'ACHAT DE CREANCES' is a factor's wording. A debt-relief payee is excepted from POS and ATM, as a known payee is (D8).
- **Step 6:**
  - Fee wording printed without FEE: the `SVC` / `SERV` charge abbreviations, overdraft, handling, batch, item and wire charges (`CHG`, `CHRG`), RBC's `INTERAC SC`, the ATM withdrawal service charge, and the French `FRAIS` when no French loan or line-of-credit word is beside it. A bare `CHARGE` or `CHG` is never a fee word.
  - Payroll providers and benefit administrators: `PAYROLL` glued to an entry-description suffix (`PAYROLLTAX`, `PAYROLLDD`…), the providers the corpus prints (Patriot Software, DataPay, Paycor, OnPay, PayWorks, Paycom, Paylocity), the benefit administrators and retirement-plan recordkeepers (HealthEquity, WageWorks, TASC, Ascensus, Human Interest, Guideline) and the French `PAIE` and `SALAIRE`. Provider, administrator and French words are read on the originator segment only, so a holder named like one of them never hides its lender. None fires on a row that names financing.
- **Step 7:**
  - The field-order payees (`FIELD_ORDER_PAYEE_FORMS`, §5): an admitted payee that the bank prints in separate fields, read on a debit no alias matched. Chase prints 'ORIG CO NAME … CO ENTRY DESCR' and Truist prints its entry description first; Amex loans and Amex card payments are read this way. The match method is `known_payee_field_order` and the rule `<state>_field_order`. D9's LOC wording still wins.
  - The glued-digit reading of the known-payee index (§4.6).
  - The debt-relief payee: read after no known payee matched, on debits, on the row without its receiver fields, so the account holder's own name never makes a row debt relief. It then stands in for the known payee. A registered lender printed in the same row still wins, and fees still come first.
- **Step 8:**
  - The mortgage abbreviations `MTG PYMT` and `MTGE PAYMENT`.
  - A transfer to the bank's `LOANS` (`TRANSFER TO LOANS`) and the bank's own `LOAN INTEREST` with no payee printed are bank loans (D5).
  - The card-payment wording gains `CREDITCARD` and Navy Federal's `CREDIT CARD RECUR`.
- **Step 10:** the Canadian, credit-union and short cheque spellings, anchored at the start and with the instrument's number: `CHQ`, `SHARE DRAFT`, `DRAFT WITHDRAWAL DRAFT`, `CHK` (and `IMAGE CHK`, `PAID CHK`) and `CK`. A label never makes a row a cheque, and a bare `DRAFT` is lender collection wording.
- **Step 11:**
  - A loan from the business's own shareholder, owner or director (`SHAREHOLDER LOAN`, `OWNER LOAN`, `DIRECTOR LOAN`, `DUE TO SHAREHOLDER`) names no lender. On a debit whose descriptor names no organisation, the row is `other`.
  - A review entity of a routed flag group takes that flag on debits, marked unconfirmed (`review_required`, match method `unconfirmed_flag_payee_alias`; §5).
  - D10's fixed label names an `MCA SERVICING` payee.

Statement-level passes, in order:
1. Duplicates (unchanged).
2. **Recurrence**:
   - today's daily/weekly promotion of financing-keyword rows;
   - plus **D6** for unknown payees with fixed daily or weekly debits. Since 5.3, D6 also skips a listed card issuer printed alone (§3 D6, §5).
3. Reversal pairs (unchanged; the pass also clears `contributes_to_flagged_totals`).
4. Operating-source context (unchanged).
5. Duplicate finalisation (unchanged; it also clears `contributes_to_flagged_totals`).

### 4.4 Credits

In `_classify_credit_revenue`, the known-payee matcher runs **before** the operating-revenue registry. A credit from a **financing group** (D1) is `non_revenue`, with match method `financing_proceeds_credit`, and sets `contributes_to_lender_credit_exclusion`. Group aliases are financing-specific: `SQUARE CAPITAL`, never bare `SQUARE`. So platform sales settlements (Square, Shopify, PayPal, Stripe) stay revenue. The payout credits of the entities in `PAYOUT_CREDIT_ENTITIES` are revenue too (D1's exception): the financing-proceeds branch skips them, and they go on to the operating-revenue path. So are a factoring payee's credits (owner, 2026-09-26). The branch skips them the same way, and their revenue comes from the operating-revenue path, so they stay in eligible deposits. Unlike a payout credit, the row is recorded as `factoring` under its payee (`matched_rule="factoring_revenue_credit"`) and carries the Factoring flag. A factoring credit that an earlier rule claims (a transfer, an insurance term) keeps that rule's state and carries no flag.

Three existing tests pin this:
- `tests/test_revenue_classification.py:440-523`
- `:475-499`
- `:502-523`

### 4.5 Unknown lenders (the potential tier)

**Naming (D11).** Before naming a payee, `_canonical_unknown_entity` removes three kinds of text:
- bank-channel prefixes (`BUSINESS TO BUSINESS ACH DEBIT`, `ELECTRONIC WITHDRAWAL TO`, `ORIG CO NAME`…);
- ACH field segments (`DES`, `ID`, `INDN`, `IND NAME`, `CO ID`, `TRACE`, `SEC`, `EED`…);
- reference tokens.

It then keeps at most four tokens.

If what remains has no organisation cue, the entity is "Unidentified lender obligation". Organisation cues are the words LLC, INC, CORP, FUNDING, CAPITAL, FINANCIAL, FINANCE, BANK, CREDIT, LENDING, ADVANCE, GROUP, HOLDINGS, SERVICES, or a registry-style company token. `CO` was a cue until 5.3, and a legal form counts only after the name's first word (D11).

Stable names also fix recurrence grouping. Today "NORTHSTAR FINANCE PAYMENT JAN 2…8" splits into five entities.

**The tab's lines (5.3, 2026-09-27).** Before 5.3, every unnamed payee of a statement shared the entity 'Unidentified lender obligation', so the Potential Lenders tab showed one line with mixed amounts and `potential_lenders_detected` counted one. Since 5.3 the tab has one line per unnamed payee key, labelled by the entity, the recurrence's cadence and the amount (`potential_payee_label`, §4.2), for example 'Unidentified lender obligation (weekly, 450.00)'. The tab, `potential_lenders_detected`, the package and the tab's click filter read the label. Each ledger row's tag keeps its entity, since the row shows its own amount. A named potential payee keeps its name and gets no label. A package joins the same label across its members, as it joins a name.

**D6 rule.** An unknown payee whose key has debits of the same amount on at least three different dates on a daily or weekly cadence, none of the excluded states, no card-purchase mark and no compensation words (D6), becomes `potential_lender` with match method `recurring_fixed_debit`, review required. The key is the payee words and the amount, plus the digits of a masked recipient account printed after `TO` when the row has one (2026-09-27). The name never takes those digits.

### 4.6 The known-payee matcher

- **One index, built once.** A single index over every group registry is built at import time. Each alias is normalised once and the patterns are compiled once. A lookup returns `(entity, group, alias)` for the **longest** matching alias across all groups, using the token-boundary rule the current matcher applies (`(?<![A-Z0-9])alias(?![A-Z0-9])`). For example, `AMERICAN EXPRESS BUSINESS LOAN` (alternative position) beats `AMERICAN EXPRESS` (credit card).
- **Run-together forms.** A registry alias written with spaces also matches its run-together form when that form is at least 8 characters long; for example, `FORWARD FINANCING` also matches `FORWARDFINANCING`.
- **Glued digits (5.3, owner ruling 2026-09-27).** In the known-payee index only (`AliasIndex(..., glued_digits=True)`), the last word of a multi-word alias also matches that word with digits glued on, when the word has at least three letters: `GOAT ADVANCE` matches `GOAT ADVANCE1234`. An alias whose last word has one or two letters stays strict (for example Bell Rock's `BELL ROCK IN FD`, an open owner question). Amendment (true revenue audit fix batch B6, I08 and I22, 2026-10-01): a credit is read with a credit index (`match_known_payee(..., credit=True)`) in which a run-together alias, one token of eight letters or more (a one-word alias, or a multi-word alias's run-together form), also matches that token with a digit run glued after it: `FORWARDFINUSA` matches `FORWARDFINUSA1`, `LCFGROUPINC` matches `LCFGROUPINC7`. A shorter one-word alias stays strict (`ONDECK` never matches `ONDECK123`), and the digits must end the token. The credit index also reads the hand-kept `CREDIT_ONLY_ALIASES` (`LCFGROUPINC`). A debit keeps the default index without either: on debits they would add lender and personal-loan readings (a PayPal eCheck to the LCF Group, two consumer lenders' names printed with a digit glued on) that the G7 allowlist has not signed off; whether they join the debit side is the owner's.
- **Reference-tied aliases (true revenue audit fix batch B6, I49, 2026-10-01; its review round 1).** An alias of the hand-kept `REFERENCE_TIED_ALIASES` matches only where a reference code (a token with a digit) or nothing follows it, in its spaced and run-together forms: Tilt's advance on the RTP network and by PNC's instant payment (`RTP CREDIT EMPOWER`, `INSTPMNTIN EMPOWER`), its card-network push (`TILT CASH`), and Brigit's two rail forms (`RTP CREDIT BRIGIT`, `INSTPMNTIN BRIGIT`). So a company named Empower… that pays by RTP (`RTP CREDIT EMPOWER SOLUTIONS …`), a person or company whose name starts with Brigit (a given name) paid on either rail, and a company named `TILT CASH …` paying by ACH are never read as the app; Tilt's longer `TILT CASH ADVANCE` is not tied.
- **The debt-relief index (5.3).** The Debt relief table (§5) has an index of its own, read by `match_debt_relief_payee` only after no known payee matched. It is never a longest-alias peer of the known-payee groups, because the matcher reads the whole row: a debt-relief alias in the holder's own name would otherwise outrank the funder. It reads run-together forms (`FORTHPAY`, `RAMPAYMENTS`), as the known-payee index does.
- **Speed.** Today one registry miss costs about 7 ms, and a 300-row statement takes about 3.2 s to classify. The new matcher must be at least **10×** faster on the same synthetic statement.

## 5. The registry

- **Where the lists live.** All names stay in `analysis/classification_registry.py`, the one module the no-hardcode guard exempts (`tests/test_no_statement_hardcodes.py:85-87`). It holds one alias table per group:
  - `LENDER_ALIASES` (MCA funders and equipment financing)
  - `ALTERNATIVE_POSITION_ALIASES`
  - `LINE_OF_CREDIT_ALIASES`
  - `CARD_ISSUER_ALIASES`
  - `VEHICLE_FINANCE_ALIASES`
  - `MORTGAGE_SERVICER_ALIASES`
  - `BANK_NAME_ALIASES` (for D5)
  - `LEASE_RENTAL_ALIASES`
  - `PERSONAL_LOAN_ALIASES`
  - `FLOOR_PLAN_ALIASES`
  - `FACTORING_ALIASES`
  - `PREMIUM_FINANCE_ALIASES`, consulted inside the insurance rule
  - `DEBT_RELIEF_ALIASES` (5.3), the Debt relief group. It is a table of its own, like `BANK_NAME_ALIASES`: it is not in `PAYEE_GROUP_REGISTRIES`, and only the debt-relief index reads it (§4.6), on debits no known payee claimed.
  - `POTENTIAL_LENDER_ALIASES`

  `CONFIRMED_LENDER_ALIASES` stays as a compatibility name for `LENDER_ALIASES`.
- **Non-lender brands (5.3).** The D6 vocabularies of non-lender brands (savings apps, vendors, government agencies, payroll providers, telecom carriers) live in the classifier, as `_PAYROLL_PATTERNS` and `_TRANSFER_PATTERNS` already do; a name joins only after a collision check against every registry table and ledger alias prints no hit.
- **Admission.** An entity enters a counted or flagged list only when the research ledger shows all of the following:
  - its identity and business type, confirmed from a public source or an unambiguous descriptor;
  - confirmation by an **independent** second agent (verdict *upheld* or *corrected*).

  *Unresolved* entities never enter a counted list. They go to `POTENTIAL_LENDER_ALIASES` (review), or they are left out and listed for an owner ruling. Since 5.3, the debits of a review entity of the vehicle, mortgage, lease, personal-loan or debt-relief group whose business type is known take that flag, marked unconfirmed (`REVIEW_FLAG_ENTITIES`); its credits keep the potential tier's exclusion. Since true revenue audit fix batch B6 (I10), the credits of a review entity of the factoring group whose business type is known are its payouts, counted and flagged, marked unconfirmed (`FACTORING_REVIEW_ENTITIES`); its debits keep the potential tier.
- **`REVIEW_FLAG_ENTITIES`** (5.3, owner ruling 2026-09-27) is rendered in the GENERATED block from the ledger (`tools/lender_ledger.review_flag_entities`). It maps each `review` entity of a routed group (`ROUTED_REVIEW_GROUPS`: vehicle financing, mortgages, leases and rentals, personal loans, debt relief) to its group, unless its `business_type` starts with `unknown` (a payee read from a payment code alone).
  - The classifier reads the map on debits only, at step 11. The potential alias that wins decides, and its entity's group decides the state. The row is flagged with `review_required`, and its flagged position says so (§6, §8.5).
  - The routed entities stay in `POTENTIAL_LENDER_ALIASES`, so their credits keep today's exclusion.
  - A review entity of the lender, potential, alternative-position or factoring group keeps the potential tier, because each has a plausible counted reading.
- **`FACTORING_REVIEW_ENTITIES`** (amendment, true revenue audit fix batch B6, I10, 2026-10-01; the lender-scope and factoring rulings of 2026-09-24 and 2026-09-26). The tier's exclusion made a factor's payouts `non_revenue`, which no reviewer could reopen, against the ruling that a factor's payouts are revenue, counted and flagged. It is rendered in the GENERATED block from the ledger (`tools/lender_ledger.factoring_review_entities`): each `review` entity of the factoring group whose `business_type` does not start with `unknown` (today Eagle Capital, Texoma Capital and Primary Capital Solutions).
  - On a credit, the classifier sends such an entity's winning potential alias to the factoring payout, as an admitted factor's credit (§4.4): the row is `factoring` under the entity, `flagged_group="factoring"`, `contributes_to_flagged_totals`, `review_required` (its flagged position says "Unconfirmed: identity under review"), match method `unconfirmed_flag_payee_alias`, rule `factoring_review_revenue_credit`. The credit revenue decision skips the potential tier's exclusion for it and reads the operating-revenue path; the true-revenue pass counts and flags it (`factoring_payout`), never verified, and a reviewer may confirm or reject it (true revenue §6.3 narrowing 10).
  - Its aliases stay in `POTENTIAL_LENDER_ALIASES`, so its debits keep the potential tier, as the 5.3 rule for the factoring group says, and every reader of that table (the cut-originator wire veto, the descriptor-proceeds and Q7 vetoes) reads it as before.
  - B6 review round 1: a credit the credit revenue path's reversal rule reads (true revenue §6.1 step 3, for example a trailing `RETURNED ITEM` that the classifier's own step 3 does not read) is not routed: a reversal is no payout, so the row keeps the reading it had before the routing (`other`, no Factoring flag, no review mark, out of the Factoring position's `count_credited`) and its non-revenue reversal decision. An admitted factor's credit with the same wording still takes the factoring class and flag (§4.4, the 2026-09-26 routing, inherited and unchanged: left unrouted, an admitted factoring alias on a credit would read as financing proceeds under D1). Whether an admitted factor's reversal should leave the Factoring position is an owner item.
- **Aliases:**
  - They come from spellings seen on real statements. They are payee names only, never customer names, amounts or account numbers.
  - Bare platform names (`SQUARE`, `SHOPIFY`, `PAYPAL`, `STRIPE`, `INTUIT`, `AMAZON`) appear only in the operating-revenue registry.
  - An alias must name the *financing* business, not a brand that also sells goods. `TOYOTA FINANCIAL`, `FORD CREDIT` and `GM FINANCIAL` are fine; `TOYOTA`, `FORD`, `APPLE` and `CAPITAL ONE` alone are not. Otherwise a card purchase at a dealership or store would become a flagged position, because card payments to known payees now bypass POS (D8).
  - BlueVine's aliases are `BLUEVINE CAPITAL` and `BLUEVINE LOAN` (owner, 2026-09-25). Bare `BLUEVINE` is not an alias: it also names Bluevine Bill Pay payments and receipts between other businesses and transfers to or from Bluevine checking accounts, which are not the line of credit. Transfer precedence alone would not protect those rows, because they are payments to and from third parties.
  - SmartPay's alias is `SMARTPAY LEASING`, the lease-to-own SmartPay Leasing (owner, 2026-09-25). `SMARTPAY SOL` names SmartPay Solutions, whose insurance premium billing is neither a lease nor financing, so no table claims it and those rows stay unflagged.
  - `ONDECK`'s `ENOVA` alias must not catch Journey Capital or NetCredit rows.
  - **One funder, one entity.** A company that prints under two names counts once. EBF Holdings, LLC does business as Everest Business Funding, so the `EBF HOLDINGS` spellings are aliases of `EVEREST BUSINESS FUNDING` (owner, 2026-09-25).
  - **An insurer's alias as a premium-finance alias.** A premium-finance alias may equal an alias of the hand-kept insurer table only on the owner's ruling. The one such spelling is `FIRST INSURANCE`, the ACH company name that FIRST Insurance Funding prints (owner, 2026-09-25). The hand-kept insurer First Insurance keeps its alias, and the insurance rule reads the premium-finance table first (§4.2).
- **Owner-ruled inputs.** Besides the validator's hand-kept lists (the payees the owner named in §2, and the bare platform and brand names), `analysis/classification_registry.py` holds four hand-kept constants for the rulings of 2026-09-25, outside the rendered tables:
  - `PREMIUM_FINANCE_INSURER_ALIASES`: the premium-finance spellings that may equal an insurer alias (`FIRST INSURANCE`);
  - `MERGED_REGISTRY_ENTITIES`: an entity of today's registry that a ledger entity absorbs (`EBF HOLDINGS` into `EVEREST BUSINESS FUNDING`);
  - `REATTRIBUTED_REGISTRY_ALIASES`: an alias of today's registry that names another company (`SMARTPAY SOL`, SmartPay Solutions);
  - `PAYOUT_CREDIT_ENTITIES`: the entities whose credits are payout revenue (D1's exception).

  A fifth came with the owner's ruling of 2026-09-27 (5.3):
  - `FIELD_ORDER_PAYEE_FORMS`: the printed forms, in the bank's field order, of admitted payees whose bank prints the originator and the entry description apart, so no contiguous alias can match them. Chase prints 'ORIG CO NAME … CO ENTRY DESCR' and Truist prints its entry description first. Today the constant holds American Express Loans and the American Express card payment. It is keyed by ledger entity, each value a regular expression read on the normalized row, on debits only, when no alias matched. The Chase forms refuse a row that holds two originator blocks (a merged row stays in review). It is hand-kept and validated against the ledger: `tools/lender_ledger.py` refuses an entity that is not admitted in a known-payee group, and a form that does not compile.

  `OWNER_NAMED_PAYEES` gained, with the same ruling, the three missing funders (Flexibility Capital, Merit Business Funding, Essentia Funding) and a `debt_relief` group (RAM Payments / Reliant, Global Holdings, Tayne Law Group; Resolve Capital is under review, so it is not listed).
- **Card issuers printed alone (5.3).** A `card_issuer_context` alias is also read the other way. On its own it does not make a row a card payment (step 8 still needs payment wording), but when the alias's words are the leading words of the D6 payee, the row is a card payment printed alone, and D6 does not take it (§3 D6). An issuer token inside a longer name (`<issuer> CAPITAL …`) is never enough, and the row must name no financing.
- **Collision audit.** `tools/lender_alias_audit.py` reads only the local cache and runs outside CI. For every alias it reports the payees it matches, and it must report **zero** matches on a different payee. The research found collisions to fix: `BLUEVINE` catches BlueVine banking, `SmartPay` catches Atlas Financial card rows, and `ONDECK` catches Journey Capital. The ledger fixes all three: bare `BLUEVINE` and bare `SMARTPAY` are dropped, and `ONDECK` claims neither Journey Capital nor an unrelated `ENOVA`.
- **Evidence ledger.** `docs/lender-registry-evidence.md` lists every entity with its group, a public source URL, the verification verdict, and, for anything unconfirmed, where the researchers looked. It contains no statement text, amounts or customer names.
- **Entities awaiting an owner ruling** are listed at the end of the ledger. Since the delegated rulings of 2026-09-25, the only one is a numbered Ontario company debited daily/weekly in about three customer accounts; it is not searched anywhere, by rule.

## 6. The payload (the contract §8 builds on)

Per account:
- **Rows.** Every `statement.transactions[].classification` carries `flagged_group` and `contributes_to_flagged_totals`, and since 5.3 `potential_payee_label` (§4.2).
- **`metrics.flagged_groups`** is `{group: {"count": int, "total": float, "count_credited": int, "total_credited": float, "payees": int}}`, built from rows with `contributes_to_flagged_totals`. `count` and `total` are the debits; `count_credited` and `total_credited` are the credits (a factor's payouts, owner 2026-09-26); `payees` counts the payees with any contributing row. It **never** feeds `lender_*`, `withholding_*`, `eligible_deposits` or `potential_*`.
- **`detection.flagged_positions`** is a list of entries, sorted within each group by total debited plus total credited, then by payee. Each entry holds:
  - `group`, `payee`, `matched_alias`
  - `count`, `total_debited` (debits only)
  - `count_credited`, `total_credited` (credits only; 0 and 0.0 without one). A payee whose counted rows are all credits has an entry with `count` 0.
  - `cadence` and `avg_gap_days`, over every counted row, debit or credit
  - `first_date` and `last_date`, likewise
  - `source_locations`
  - `review_required` (5.3, last): true when any counted row of the payee requires review, which today only a routed unconfirmed payee's row does (§5). The package's flagged items and the statement and package exports (CSV/XLSX) carry it too, last.
- **`detection.potential_lenders`** (5.3): an unnamed payee's entry is named by its label, so its `funder` is the `potential_payee_label` and each payee key is its own entry (§4.5).
- **Cadence** comes from a new helper that returns `daily`, `weekly`, `biweekly`, `monthly` or `irregular`. `classify_cadence` and today's promotion gate stay unchanged.
- *Amendment (owner request 2026-10-06, R2-OW18):* **`detection.lender_payment_changes`** lists the statement's lender payment changes (a decrease, an increase, a schedule change, a pause, a new concurrent stream or a stop of a confirmed funder's or a potential lender payee's regular payment; `analysis/lender_payment_changes.py`). Information only: no lender count, total, withholding, flag or revenue figure reads it (true revenue spec §9.1).
- **Versions:**
  - `CLASSIFICATION_VERSION = "5.0"`.
  - `ANALYSIS_STAGE_VERSION` goes 18 → 19 in the same commit (`webapp/artifact_cache.py`), so a re-upload does not reuse a stale analysis. OCR stays cached.
  - The D6 clarification (2026-09-26) changes stored rows again: `CLASSIFICATION_VERSION = "5.1"` and `ANALYSIS_STAGE_VERSION` 19 → 20, together.
  - So does the second D6 clarification (2026-09-27: compensation memos, masked recipient accounts): `CLASSIFICATION_VERSION = "5.2"` and `ANALYSIS_STAGE_VERSION` 20 → 21, together.
  - The false-potential release (2026-09-27) changes stored rows: `CLASSIFICATION_VERSION = "5.3"` and `ANALYSIS_STAGE_VERSION` 21 → 22, together.
  - So does the owner's Idea Financial ruling (2026-09-28: a counted lender, no longer a line of credit): `CLASSIFICATION_VERSION = "5.4"` and `ANALYSIS_STAGE_VERSION` 22 → 23, together.
  - So does the owner's Amerifi Capital ruling (2026-10-11: a counted lender, read as a potential lender until then): `CLASSIFICATION_VERSION = "5.9"` and `ANALYSIS_STAGE_VERSION` 37 → 38, together (5.5 to 5.8 and stages 24 to 37 are the true revenue spec's, its §9.3).

## 7. Command-line tools, benchmark, docs

- `batch.py` gains a `flagged_positions` column (`group:payee` list), and `analyze.py` prints a Flagged positions block. Both run at analysis time and do not read Settings.
- *Amendment (owner request 2026-10-06, R2-OW18):* `batch.py` gains seven columns after `recurring_debit_groups` (the decreases, increases, schedule changes, new streams, pauses and possible stops, and `lender_payment_changes`, each item as `kind:label`), and `analyze.py` prints a "Lender payment changes" block after the potential lenders (true revenue spec §13).
- `benchmark/lenders.py` and `benchmark/compare.py`: MoneyThumb lenders that we now flag are reported as *flagged here*, not as misses. `NON_MCA_SCOPE` is replaced by the flagged groups.
- `docs/transaction-classification.md`: update the state list, the precedence and the extension rule.
- `docs/moneythumb-replacement/R1_HARDCODE_LOG.md`: record that the owner moved `INTUIT FINANCING` (item 12a) to alternative positions on 2026-09-24.

## 8. Webapp

### 8.1 Settings

- `webapp/settings.py` `DEFAULTS` gains the `flag_*` keys, one per flag group, each `True`. Since the Debt relief group (5.3, `flag_debt_relief`) there are twelve checkboxes.
- The `GET/POST /api/settings` routes do not change.
- The tests that compare the whole settings dict are updated.

### 8.2 Serving

`_displayed(analysis, *, settings=None)` reads Settings once, when no snapshot is passed. It applies the NSF basis, then the new `apply_flagged_groups_to_payload`. That function:
- **copies before it changes anything.** It copies each account's `statement.transactions`, `detection` and `metrics`. `apply_nsf_basis_to_payload` copies shallowly, and the stored job must never be touched;
- removes unticked groups from `metrics.flagged_groups` and `detection.flagged_positions`, their credited fields included;
- sets `flag_shown: bool` on each copied row's classification, a flagged credit row included;
- adds `analysis_rules_outdated: true` when a stored record carries no `classification_version`, or one older than the running `CLASSIFICATION_VERSION`, compared as numbers (major, then minor); a version it cannot read marks nothing;
- never refuses. Payloads without the new fields pass through unchanged.

`_package_members` reads the whole settings snapshot once per package, as it already does for NSF, and passes it to `_displayed` and to `_package_analysis`.

### 8.3 Package

- **Roll-up.** `_package_analysis` adds `flagged_positions: {group: [{payee, documents, count, total_debited, count_credited, total_credited, cadence, first_date, last_date}]}`, built from the rows of each validated member for the ticked groups:
  - internal-transfer legs are excluded;
  - evidence carries `source_account`;
  - a debit adds to `count` and `total_debited`, a counted credit (a factor's payout, owner 2026-09-26) to `count_credited` and `total_credited`;
  - cadence is computed across all members' dates, debits and credits alike;
  - items are ordered by total debited plus total credited, then by payee.
- **Totals.** `flagged_position_count` and `flagged_position_total` (the debits) are added, and `flagged_position_count_credited` and `flagged_position_total_credited` (the credits, owner 2026-09-26).
  - The money keys join `_CROSS_CURRENCY_TOTAL_KEYS` and `EXPECTED_REFUSED_TOTALS`.
  - The counts join `UNIT_FREE_TOTALS`.
  - `total_debited` is already a refused roll-up key, and `total_credited` joins it.
  - A refused package orders roll-ups by count (debits plus credits), then by name.
- **Untouched:** lender totals, withholding, and the `decision` rule (D7).
- *Amendment (owner request 2026-10-06, R2-OW18):* the package reads each lender payment series across the consecutive statements of one account (`_package_lender_payment_changes`: R2-OW15's `_same_account`, 5 days of overlap to 7 days of gap), publishes `lender_payment_changes` and the members it could not check (`lender_payment_changes_unchecked`, with their reasons), and never sums or rolls them up; lender totals, withholding and the decision are untouched (true revenue spec §9.2).

### 8.4 Downloads

- **Single-statement CSV/XLSX:** readable `flagged_<group>_<n>` rows (payee, count, total, count and total credited, cadence) for ticked groups only, through the escaped-row path.
- **Package CSV/XLSX:** `flagged_<group>_<n>` rows. The currency sweep's `CROSS_DOCUMENT_SECTION` widens to cover them, the credited fields included.
- **JSON:** follows the displayed payload automatically.
- *Amendment (owner request 2026-10-06, R2-OW18):* the statement downloads write `lender_payment_change_<n>` sections (no JSON cell for the detection key) and the package downloads `lender_payment_change_<n>` and `lender_payment_unchecked_<n>` sections, each change in its own statement's unit (true revenue spec §10.8).

### 8.5 Dashboard

- **Settings.** A new "Flagged positions" section sits between Analysis and Statements, with its own status line.
  - The checkboxes are rendered from one JS constant into a container.
  - One delegated `change` listener saves one key per change, then calls `refreshShownResults()`.
  - The whole group is disabled while a save is in flight.
- **Flagged positions panel.** It sits on the results page, the package page and the statement modal.
  - Columns: Group, Payee, Count, Total, Cadence, plus Statements on the package page.
  - What a payee paid in (a factor's payouts, owner 2026-09-26) is shown under its Count and Total as "received", never added to them.
  - Money is shown with the payload's currency.
  - Clicking a payee filters the ledger.
  - An empty state says no ticked group has payments.
  - The header text must not reuse "Potential Withholding", "Eligible Deposits" or "Exposure".
  - A payee whose position carries `review_required` (5.3, a routed unconfirmed payee) shows the line "Unconfirmed: identity under review" under its name.
- **Transaction tags.**
  - Each new state gets a label. The Debt relief state (5.3) has the tag glyph "DRP" and the label '<entity> (Debt relief)', or 'Debt relief' when no entity is named.
  - A row with `flag_shown` carries a "Flagged" chip.
  - A credit shows its revenue state first (unchanged). A factoring credit shows both its revenue state and the chip.
  - A "Flagged" ledger filter pill is added. It keeps flagged credit rows as well as debits.
  - When the group being filtered is unticked, the ledger filter resets.
- **Lender table.** No change beyond its now-correct contents. Since 5.3 the Potential Lenders tab lists each unnamed payee key on its own labelled line ('Unidentified lender obligation (weekly, 450.00)', §4.5), and clicking a line filters the ledger by that label.
- *Amendment (owner request 2026-10-06, R2-OW18):* the lender table shows one warning line per lender payment change above its rows ("Payment decreased: …", "Payment schedule changed: …", "Payments paused: …", "New payment stream: …", "Possible stop: …", or in a package "No payment to … since …"), potential lenders' lines in the neutral tone, and a neutral "not checked" line where the payload predates the check; no lender row, count or chip changes (true revenue spec §10.1).
- **Outdated notice.** When `analysis_rules_outdated` is set, the results page shows "Analysed with older lender rules" and a **Re-analyze** button (§8.6).

### 8.6 Re-analyzing a saved statement (D12)

`POST /analysis/<job_id>/reanalyze` re-runs the analysis for a saved job.

1. It reads the job's stored PDF bytes, which are kept on disk by content hash.
2. OCR is served from the cache. The saved reading is the only one used: a statement whose reading is not cached is refused, and no reader runs (owner, 2026-09-26; S5's Decision 2).
3. It **replaces the job's analysis in place**. The job id and its place in Recent do not change.
4. The previous analysis is kept in the audit log.
5. Revenue review decisions are **replayed** from `review_decisions` onto the new analysis. A decision is replayed only when the row at the same account and location has the same description and amount. Anything that cannot be replayed is reported back: "N reviews need redoing". A decision whose row a rule of the new analysis now decides is reported apart, as decided by the rules, and is not counted as needing redoing (owner, 2026-09-26; S5's Decision 5).

The route refuses when the stored PDF is missing.

## 9. Proof

- **Tests**, all with fabricated descriptors and never statement text:
  - classification tables for every group, both directions, including the card-paid lender (D8), LOC wording (D9), unnamed loans (D5), unnamed equipment financing (D4), the D6 recurrence rule and D11 naming;
  - the credit-side financing proceeds, platform settlements that stay revenue, and the payout credits of D1's exception;
  - factoring payouts that stay revenue and carry the Factoring flag (owner, 2026-09-26), counted apart from the debits in the payload, the package, the exports and the dashboard;
  - Settings, serving and exports for every checkbox, with the stored record unchanged;
  - the package roll-up and the currency refusal;
  - the dashboard through `tests/webapp_js_harness.py`;
  - re-analysis with review replay.
- **Pins that move, re-pinned with derived totals only:**
  - ATB November (BDC leaves the lenders; Econolease joins them)
  - TD CMCA (CMCA Finance joins the lenders and leaves the potential tier)
  - Altana (Affirm leaves; NMEF joins)
  - first_farmers (its BlueVine-named row is a payment to another business that banks with Bluevine, so it is neither a lender nor a LOC)
  - `SBA LOAN PAYMENT`, the Affirm card purchase, and De Lage Landen
  - Intuit (item 12a)
  - NMEF, Navitas and Balboa
  - `ANALYSIS_STAGE_VERSION`
- **Before/after census** (`tools/lender_census.py`, local only), over the 7,241 cached analyses. For each analysis it reports lenders gained and lost, flagged groups (the debits, and the credits since the owner's ruling of 2026-09-26), eligible-deposit moves and the change in the withholding rate. Acceptance:
  1. Every gained lender traces to an admitted ledger entity.
  2. Every lost lender is a ruled move. CAPITAL INFUSION leaves for Alternative positions, a ruled move. The census reads the EBF merge as one lender (`MERGED_REGISTRY_ENTITIES`), so EBF HOLDINGS shows neither as lost nor as gained: its rows are EVEREST BUSINESS FUNDING's.
  3. The alias audit reports zero collisions.
  4. The owner's NMEF statement shows NMEF as a lender and Truist as a bank loan.
  5. No statement gains a lender from a generic word.
  6. The factoring ruling (owner, 2026-09-26) moves no lender, and it moves eligible deposits only where factoring credits are. On S2's code before and after the ruling, the census counts no lender gained or lost. Factoring's credits show as flagged credits, and eligible deposits rise only in the accounts that hold them. The measurement of 2026-09-26 found 1,174 credits, with eligible deposits up in 157 accounts and unchanged in the other 7,084.
  *Amendment (owner request 2026-10-06, R2-OW18):* the census's snapshot gains one key, `lender_payment_changes`, and its compare a `lender_payment_changes` block (counts by kind and state, the accounts not comparable, the items gained and lost), new outputs only: they never fail G7, and with the key removed the snapshot is byte-identical to its base (true revenue spec §14.3).
- **Speed:** the 300-row synthetic statement classifies at least 10× faster than today.

## 10. Services

The owner's standing rule applies: one Opus 5.5 agent per service, then an independent Opus reviewer, and the orchestrator checks every report's evidence before accepting it.

| # | Service | Owns | Starts after |
|---|---|---|---|
| S1 | Registry & matcher | §4.6, §5: compiled matcher, group registries from the ledger, alias fixes, collision audit, evidence ledger | this spec |
| S2 | Classifier & analysis payload | §4.1-4.5, §6, §7: states, rule order, credits, the potential tier, metrics/detection/serialization, cadence helper, versions, CLI, benchmark, docs, re-pins | S1 |
| S3 | Webapp serving, package & downloads | §8.1-8.4 | S2's payload contract (§6); may start against fixtures built from §6 |
| S4 | Dashboard | §8.5 | §6 and §8.2's `flag_shown` / `analysis_rules_outdated` |
| S5 | Re-analysis of saved statements | §8.6 plus its notice in the dashboard | S2 |

- **Order.** S1 runs first, then S2. S3, S4 and S5 run in parallel against the §6 contract, and each finishes once S2 lands.
- **Checks.** At the end the orchestrator runs the census, the alias audit, the targeted test selections and a browser check of the dashboard.
- **Merge and hosting.** The branch merges into `text-first-v1` after all reviews close. The Fly tryout is not updated unless the owner asks.

## 11. Out of scope

- Learning from analyst decisions (marking a potential lender as a lender, position or LOC in the app, remembered for future statements). This is the next project.
- Whether Affirm merchant payouts are revenue (D2).
- Revenue changes beyond financing proceeds.
- The text-first reader.
