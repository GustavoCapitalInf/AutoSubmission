# Orchestration model policy — BINDING (Gustavo, 2026-09-02, during Phase 2.1)

```
STATUS: ORCHESTRATION-POLICY OVERRIDE — supersedes every historical model-routing statement
AUTHORITY: Gustavo, 2026-09-02 (explicit user instruction to Ocean, recorded verbatim in meaning)
SCOPE: orchestration only — no Phase 2.1 scope change, no engineering redo, no proof invalidation
```

## The override

The historical Phase 2.0 model-routing policy — implementation cells on **Sonnet 5 (HIGH)**,
adversarial reviews and re-reviews on **Opus 5** — is **SUPERSEDED**. Effective immediately:

* Ocean remains the lead orchestrator in **Fable 5.1**.
* **No new Sonnet 5 subagents** are launched.
* **No new Opus 5 reviewers or re-reviewers** are launched.
* Historical references to Sonnet 5 / Opus 5 in Phase 2.0 handoffs, cards, reviews or
  orchestration documents **no longer have model-selection authority**. They stay in those
  documents as the record of what happened; they do not instruct.
* The ROLES and the independence requirements of those documents are PRESERVED:

  ```
  implementation -> independent adversarial review -> reproduce findings -> closure -> independent re-review
  ```

  performed using the currently authorized Fable 5.1 orchestration environment. Independence
  still means: the reviewer did not write the code; reads only the rulings, the card, the diff and
  the tests; reproduces every finding before claiming it; an implementation never approves itself.

## What is NOT changed by this override

* Already-completed Phase 2.1 work is **not restarted or discarded** because Sonnet 5 or Opus 5
  produced it.
* Already-green tests and proof results are **not invalidated** because of which model produced
  them.
* Cell R's closure, in flight at the time of the override, **finishes as-is**.
* Phase 2.1 scope, the Phase 2.0 safety invariants, the rulings, the floor — untouched.

After the in-flight closure: any still-required review or re-review is performed in the current
Fable 5.1 orchestration environment; composition, the floor, the cold/replay proof, CI and the
closure continue normally.

## Model-selection precedence (binding for Phase 2.2 and every later phase)

1. **the current explicit user instruction**
2. **the current phase's instructions / card**
3. **durable safety / architecture rulings**
4. **historical orchestration guidance**

A historical model name never overrides a newer explicit user instruction. A future phase that
inherits a Phase 2.0 card, rule file or review must read the model names there as history, not as
an instruction, unless the current phase's instructions or the user say otherwise.

## Documents corrected under this override (2026-09-02)

* `docs/moneythumb-replacement/PROJECT_STATUS.md` §Standing rules — the "all delegated agents run on
  Claude Opus 5" rule replaced by a pointer to this file.
* `docs/moneythumb-replacement/PHASE2_RULINGS.md` — the 2026-09-01 "Models" authorization line
  annotated as superseded by this file (Gustavo's 2026-09-01 wording kept as the record).
* `docs/agent-handoffs/PHASE2-RULES.md` — the precedence rule added.
* `docs/agent-handoffs/PHASE2-1-PADDLE.md` §Adversarial review plan — "Opus" replaced by "the current
  orchestration environment".
* The cell cards `P21-*.md` and every Phase 2.0 card / review keep their historical model names
  unchanged; this file is the authority over them.
