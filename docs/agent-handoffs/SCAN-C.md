# Agent Handoff - SCAN-C (batch 4 refill; SCAN-SCOUT card C)
Ocean reviews and merges; you never merge or push.
**Scout-measured: credit count + credit total reconcile to the cent on
10 of 10 readable docs in prototype (proto_gulf.py / proto_two.py in
scratchpad scan-scout-5fb5b603/). Confidence HIGH. 11 docs, 0 validated
today.**

# Identity
- **Agent:** SCAN-C - the Gulfport-masthead core processor (the issuer
  names itself Hancock Whitney in the body - read it from the document;
  if identification does not meet the masthead/corroboration bar, the
  honest-unknown-issuer policy applies: bank=None beats a guess).

# Git ownership
- Base: main `707ba9e` - Branch: `wave4-scanc` - Worktree:
  `.claude/worktrees/mt4-scanc`. Own: one NEW module, registry entry
  (NEW only), tests, W3 log (#SCANC).

# Population (11 distinct shas, all scanned/failed/unclaimed)
1106E3FDD20A02A40704062BD00B99406B34D42D651CD21D6FD19D0FB3C0AE14
5AFC66416A6620817EFD9EACD196DE8DDD29BDCECC05BA1C76DA9FEE5BA91E8B
6F907373781E199D1BE2B042BFB1278C72C02AC041E78B0E25FBD9589E5A50BD
749CDCE460CB61F10D903A0BB442E18030E901A2BFB61D95428A2AAB83A9B3FE
B8B2136D2B41608E8D604E02B81ABFE2CADB1DFB424ED49CDAE6B416133251A7
DC3881234577C378085130583A01A627F0A8BDADA44F745AA56965EF1C8F53C2
DCB80E04B8EDEDC4DCF10B45976164375A9E6A93F35E003163E3B82DB21EB4D2
E4F5802ECAFE626F7048D69B463A1BBA5D0A66B8535136CCCB5B7CB36E3FBE16
F7BD156A7C863DCB20A77C4C22E76F7629DD1B82F514946AAECAA80ACB895205
F8FC1D8B3ECD3F304130D4BE83BDB4BB08DA30FD0153270F5F025D3AA75D51C8
FA59082D6A74CC1D4E10BFC2E70F96E74EB164E3CA01B310373E58E77D78756E
(F7BD156A7C86: 2 pages, unreadable summary - MUST stay refused, named.)

# Printed shape + oracle (seven independent constraints)
PREVIOUS BALANCE b0 / + N CREDITS C (deposits EXCLUDING the interest
credit) / - M DEBITS D (debits EXCLUDING service charges) / - SERVICE
CHARGES S / + INTEREST PAID I / ENDING BALANCE b1, with
b0 + C - D - S + I == b1; two-column Date Amount Description grids
under Deposits and Other Credits / Checks / Other Debits; a Balance By
Date grid as the independent walk. **THE TRAP (scout-proven): the
service-charge/interest partition. Lumping them into DEBITS/CREDITS
produces a plausible statement whose counts silently disagree - the
scout's v2 prototype mis-modelled it and failed loudly on all 11, which
is the oracle biting. All six figures + identity + the date grid must
hold simultaneously.** Two-column grids invite row duplication; the
count check is the guard (fixture it).

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-14 batch-3 entry in WAVE2_EXECUTION_LOG.md
first. Base main `ea8d8e8` (v11, registry 68, suite 3,769). Run of record:
`discovery_reports/2026-08-14T214345.671986-0000-d5c75ff6` (validated 2,357 /
review 22 / withheld 69 / failed 919 / deferred 13; 3,380 distinct shas).
Archive + caches READ-ONLY; OCR artifacts by DIRECT file path only (never
open the webapp_data sqlite index - it writes on read); $0 vendor spend;
private uniquely-named scratchpad subdir (cells have collided on the shared
top level). Long background shells get killed - run long proofs as
SEQUENTIAL single commands. Proof floor per branch: full default suite +
corpus-marked slice (MANDATORY - the corpus gate is structurally blind to
review<->validated movement inside its PASS bucket; proven in batch 3) +
`python corpus_gate.py` GREEN 106/3 + guards + conformance cross-product;
exit codes verbatim; every mover named by content_sha256 + outcome + field;
claimed != validated; zero movement outside your named populations; commit
incrementally with clean tree at the end; NEVER merge or push - Ocean runs
the train. ANALYSIS_STAGE_VERSION bump is Ocean's at merge. Fail-closed
everywhere: a document you cannot prove publishes nothing.


# Final report to Ocean
Per-doc outcomes (11 named); the partition design; sweeps; proofs;
commits; risks.
