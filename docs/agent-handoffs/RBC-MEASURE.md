# Agent Handoff - RBC-MEASURE (batch 6, card 11 - READ-ONLY: the RBC currency measurement packet)

Ocean reviews; you never merge or push.
**You change NOTHING in the repo: no branch commits beyond your report
file, no code edits, no expectation edits, no cache writes. Prototype
probes live in your private scratchpad subdir only. Your product is the
eight-proof evidence packet.**

# Identity
- **Agent:** RBC-MEASURE - produce the read-only measurement packet
  Gustavo requires BEFORE any RBC currency ceremony. Read
  docs/moneythumb-replacement/CURRENCY_DOCTRINE.md sections B and C first;
  they are the ruling verbatim. The doctrine is a bank/account-jurisdiction
  default - NOT the rejected `absence of "U.S. Funds" => CAD` framing.

# Git ownership
- Base: main (the doctrine commit) - Branch: `wave6-rbcmeasure` - Worktree:
  `.claude/worktrees/mt6-rbcmeasure`. Own: your report file
  `docs/moneythumb-replacement/RBC_CURRENCY_MEASUREMENT.md` on the branch,
  W3 log (#RBCMEASURE). NOTHING else.

# The population
The prior scouting named ~151 documents (including all 4 pinned RBC docs)
whose published currency would move under an RBC-Canada CAD default.
RE-DERIVE the population from run
`discovery_reports/2026-08-16T000943.012887-0000-2e3ea385` + live artifact
replay - do not trust the prior count. Note batch 5's CURRENCY-1 landed
evidence-based currency readers (9 movers, empty ceremony) AFTER that
scouting; the population may have shifted.

# The eight proofs (all must land; quote the doctrine item you satisfy)
1. Every affected document is actually an RBC CANADA account/product for
   which CAD is the correct native default - name the structural evidence
   per document class (institution identity, product wording, jurisdiction
   markers: transit/institution number shapes, FR/EN furniture, postal
   codes, RBC royalbank.com vs rbcbank.com (US) domains - whatever the
   documents actually print; enumerate the evidence classes you used).
2. None contains explicit USD or other contrary currency evidence
   (`U.S. Funds`, U.S. Dollar wording, USD account designation, or
   equivalent). Show your detector text and its hit census over all 151.
3. RBC U.S. institution/products CANNOT be swept in: show the discriminator
   and prove it on any RBC-US-shaped documents in the archive (if none
   exist, prove the discriminator on synthetic printings + say so).
4. The four pinned RBC documents individually enumerated: path, sha,
   current pinned expectations, proposed movement.
5. Exact before/after currency values for every document in the packet.
6. Currency label movement ONLY: no financial amount, ADB value, ledger
   math, classification, or validation outcome changes. Prove by field
   diff over the full published block per document (prototype the default
   in scratchpad, replay, diff - READ-ONLY, private cache namespace if any
   caching at all).
7. The nine explicit-evidence CURRENCY-1 corrections remain byte-identical.
   Name all nine by sha.
8. The rule as implemented-to-be is structural (bank/product/jurisdiction
   evidence), never filename/folder. Your prototype must not read paths.
Also report: any document with CONFLICTING or uncertain evidence - the
doctrine says fail closed / preserve uncertainty; those documents leave the
packet and are named separately.

# Output
The packet document (committed on your branch only) + the ceremony-ready
enumeration (four pinned expectation diffs + the exact N-document movement
list) IF AND ONLY IF all eight prove clean. If any proof fails, the packet
reports the failure honestly - do not weaken any check to make the
ceremony pass (doctrine verbatim).

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-16 batch-5 entry in WAVE2_EXECUTION_LOG.md
first. Base carries v13, OCR v3, registry 72, suite 4,511, corpus-marked
27, gate verdicts 102/4/3. Run of record:
`discovery_reports/2026-08-16T000943.012887-0000-2e3ea385` (validated 2,430 /
review 15 / withheld 63 / failed 859 / deferred 13; 3,380 distinct shas).
Archive + caches READ-ONLY; OCR artifacts by DIRECT file path only (never
the webapp_data sqlite index); $0 vendor; private uniquely-named scratchpad
subdir. Long background shells get killed - run long probes as SEQUENTIAL
single commands; detached-process aliveness via `tasklist`, never MSYS
`kill -0`. Family populations by live detection replay or artifact-store
enumeration, NEVER rows.csv parser_id alone. Exit codes verbatim; every
document named by content_sha256; NEVER merge or push - Ocean runs the
train. Machine is shared with nine build cells: keep probes light,
sequential, and cache-read-only.

# Final report to Ocean
The eight proofs in order, each with its census and method; the
conflicting-evidence exclusions; the ceremony-ready enumeration or the
honest failure; risks.
