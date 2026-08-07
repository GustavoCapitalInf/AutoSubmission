"""Reading a discovery run back as evidence, hash-keyed and masked.

Both W3-4 commands (`discovery.adjudicate`, `discovery.compare`) read finished
run directories rather than re-running anything, so adjudication and
coverage-movement reporting cost nothing and can be redone at any time over
the frozen artifacts.

**Identity is `content_sha256`, everywhere.** That is what makes two runs
comparable without caring about ordering, run ids, timings, record ids or
which tranche mode produced them - and it is the same identity telemetry
already uses.

**Sensitivity.** The telemetry JSONL is non-sensitive by construction
(H3_SCHEMA I1) and is the primary source. `rows.csv` is the runner's
human-facing artifact and DOES carry relative paths, the extracted bank label
and a masked account fragment; this module reads exactly three of its columns
- `content_sha256`, `folder_label`, `dedup_status` - and nothing here ever
returns a path, a filename, an extracted bank label or an account fragment.
Folder labels are analyst-assigned bank names, already published in
`DISCOVERY_COMBINED_REPORT.md`; paths are not, because customer names live in
them.

**The cache-hit hole, and why the join exists.** H3_SCHEMA §5.4 declared it:
on a D-3 analysis cache hit `analyze_markdown` never runs, so the record
carries `dispatch.source = "cached"/"unavailable"` and no `parser_id`. That is
benign for coverage and fatal for W3-4, because "failure class x parser" needs
the parser. Measured on the archive runs:

    ec400125 (tranche 1, first pass)  608 withheld, 608 with a parser_id, 0 diagnosed
    02e90a86 (the W3-2 baseline)      614 withheld,   0 with a parser_id, 614 diagnosed

So the baseline cannot answer its own question alone. `parser_index` fixes it
by joining a companion run on the content hash: the parser claim is a property
of the document and the registry, not of the run that happened to observe it,
so recovering it from another run over the same bytes is sound - and it is
recorded in the output as an enrichment, never silently merged.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

TELEMETRY_FILE = "telemetry.jsonl"
ROWS_FILE = "rows.csv"
SUMMARY_FILE = "summary.json"

#: The only `rows.csv` columns that may cross into a W3-4 artifact.
ADMISSIBLE_ROW_COLUMNS = ("content_sha256", "folder_label", "dedup_status")

#: Folder labels that are not bank labels: a human sorted these as "I could not
#: sort these". They are the generic-understanding test set, not a bank.
UNLABELLED_FOLDERS = frozenset({"misc", "others", "unidentified", "(root)", "root"})


@dataclass(frozen=True)
class Document:
    """One document in one run, masked. No path, no name, no bank label."""

    content_sha256: str
    outcome_class: str
    outcome_reason: str
    dispatch_outcome: str | None
    dispatch_source: str
    parser_id: str | None
    parser_enriched_from: str | None       # run id a joined parser_id came from
    near_miss: tuple[str, ...]
    exceptions: tuple[tuple[str, str, str], ...]
    classification: str
    page_count: int
    byte_size: int
    valid_pdf: bool
    encrypted: bool
    malformed_page_count: int
    source_path: str
    truncated_page_count: int
    diagnostics: dict
    folder_label: str | None = None
    dedup_status: str | None = None

    @property
    def primary_class(self) -> str | None:
        return self.diagnostics.get("primary_class") if self.diagnostics.get("evaluated") else None

    @property
    def is_unlabelled_folder(self) -> bool:
        return (self.folder_label or "").strip().lower() in UNLABELLED_FOLDERS


@dataclass
class Run:
    run_id: str
    directory: Path
    documents: dict[str, Document] = field(default_factory=dict)
    enrichment_runs: tuple[str, ...] = ()
    folder_labels_available: bool = False
    #: Telemetry records read. Larger than `len(self)` when the archive holds
    #: the same bytes under more than one path - documents are keyed by content
    #: hash, so duplicates collapse into one, and the difference is reported
    #: rather than left as an unexplained shortfall against the run summary.
    records: int = 0

    def __len__(self) -> int:
        return len(self.documents)

    def values(self):
        return self.documents.values()


def read_telemetry(directory: Path) -> list[dict]:
    path = Path(directory) / TELEMETRY_FILE
    if not path.is_file():
        raise FileNotFoundError(f"no {TELEMETRY_FILE} in {directory}")
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def read_folder_labels(directory: Path) -> dict[str, tuple[str, str]]:
    """sha -> (folder_label, dedup_status), the only admissible row columns.

    Absent `rows.csv` is not an error: the telemetry alone is enough for every
    parser- and check-keyed cluster, and only the folder-keyed ones thin out.
    """
    path = Path(directory) / ROWS_FILE
    if not path.is_file():
        return {}
    labels: dict[str, tuple[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip()
            if sha:
                labels[sha] = (
                    (row.get("folder_label") or "").strip(),
                    (row.get("dedup_status") or "").strip(),
                )
    return labels


def parser_index(directories: list[Path]) -> dict[str, tuple[str, str, str]]:
    """sha -> (parser_id, dispatch_outcome, run_id) from a run that dispatched it.

    First writer wins, so passing the earliest live run first makes that run
    the authority. Only records with a real parser id are indexed: a
    cache-served record has nothing to contribute and must not overwrite a
    real claim.

    The dispatch OUTCOME travels with the parser id deliberately. Recovering
    `parser_id` without it leaves the document looking like it never
    dispatched, and every cluster keyed on "was this claimed" - misfiled
    labels, claims in unlabelled folders - then silently fails to form. Both
    facts have the same provenance and the same justification, so they move
    together.
    """
    index: dict[str, tuple[str, str, str]] = {}
    for directory in directories:
        for record in read_telemetry(directory):
            dispatch = record.get("dispatch") or {}
            parser = dispatch.get("parser_id")
            sha = ((record.get("document") or {}).get("content_sha256") or "")
            if parser and sha and sha not in index:
                index[sha] = (
                    parser,
                    dispatch.get("outcome") or "claimed",
                    record.get("run_id") or str(directory),
                )
    return index


def load_run(
    directory: str | Path,
    *,
    enrich_parsers_from: list[str | Path] | None = None,
    with_folder_labels: bool = True,
) -> Run:
    """One run directory, as masked hash-keyed evidence."""
    directory = Path(directory)
    records = read_telemetry(directory)
    labels = read_folder_labels(directory) if with_folder_labels else {}
    enrich_dirs = [Path(item) for item in (enrich_parsers_from or [])]
    enrichment = parser_index(enrich_dirs) if enrich_dirs else {}

    documents: dict[str, Document] = {}
    enriched_from: set[str] = set()
    for record in records:
        document = record.get("document") or {}
        sha = document.get("content_sha256") or ""
        if not sha:
            continue
        dispatch = record.get("dispatch") or {}
        source = record.get("source") or {}
        outcome = record.get("outcome") or {}
        parser = dispatch.get("parser_id")
        dispatch_outcome = dispatch.get("outcome")
        enriched: str | None = None
        if not parser and sha in enrichment:
            parser, enriched_outcome, enriched = enrichment[sha]
            dispatch_outcome = dispatch_outcome or enriched_outcome
            enriched_from.add(enriched)
        folder, dedup = labels.get(sha, (None, None))
        documents[sha] = Document(
            content_sha256=sha,
            outcome_class=outcome.get("class") or "unknown",
            outcome_reason=outcome.get("reason") or "",
            dispatch_outcome=dispatch_outcome,
            dispatch_source=dispatch.get("source") or "unavailable",
            parser_id=parser,
            parser_enriched_from=enriched,
            near_miss=tuple(
                name for name, score in (dispatch.get("scores") or []) if score < 0.5
            ),
            exceptions=tuple(
                tuple(entry) for entry in (dispatch.get("exceptions") or [])
                if isinstance(entry, list) and len(entry) == 3
            ),
            classification=document.get("classification") or "unknown",
            page_count=document.get("page_count") or 0,
            byte_size=document.get("byte_size") or 0,
            valid_pdf=bool(document.get("valid_pdf")),
            encrypted=bool(document.get("encrypted")),
            malformed_page_count=document.get("malformed_page_count") or 0,
            source_path=source.get("path") or "none",
            truncated_page_count=(source.get("truncation") or {}).get(
                "truncated_page_count"
            ) or 0,
            diagnostics=record.get("diagnostics") or {},
            folder_label=folder,
            dedup_status=dedup,
        )

    run_id = records[0].get("run_id") if records else directory.name
    return Run(
        run_id=run_id or directory.name,
        directory=directory,
        documents=documents,
        enrichment_runs=tuple(sorted(enriched_from)),
        folder_labels_available=bool(labels),
        records=len(records),
    )


def normalise_label(label: str) -> str:
    """Same normalisation `discovery.report.folder_agreement` uses."""
    return "".join(character for character in (label or "").lower() if character.isalnum())


def registered_bank_tokens() -> frozenset[str]:
    """Normalised tokens for every bank the registry has a parser for.

    Read from the live registry rather than listed here, so "do we already have
    a parser for this bank" cannot drift and no bank name becomes a constant in
    this file (the R-1 rule).
    """
    from analysis import parser_registry_entries  # noqa: F401  (populates)
    from analysis.parser_registry import registrations

    tokens: set[str] = set()
    for registration in registrations():
        for raw in (registration.id, registration.bank):
            token = normalise_label(raw or "")
            if token:
                tokens.add(token)
    return frozenset(tokens)


def registration_labels() -> dict[str, frozenset[str]]:
    """parser id -> the normalised labels that parser legitimately answers to.

    Its registry id AND its registered bank name. Both are OUR constants, so
    using them is admissible where `Statement.bank` (read out of the document,
    and forbidden by H3_SCHEMA I1) is not.

    This is what stops the label check from manufacturing findings. `td_us` is
    registered as "TD Bank", so a document a human filed under `TD Bank/` and
    `td_us` claimed is in the RIGHT folder - matching the id alone would call
    28 correctly-parsed statements misfiled, which is precisely the failure
    `discovery.report.folder_agreement`'s docstring warns about.
    """
    from analysis import parser_registry_entries  # noqa: F401  (populates)
    from analysis.parser_registry import registrations

    return {
        registration.id: frozenset(
            token for token in (
                normalise_label(registration.id),
                normalise_label(registration.bank or ""),
            ) if token
        )
        for registration in registrations()
    }


def label_agrees(folder_label: str, labels: frozenset[str]) -> bool:
    """Containment in either direction against any admissible label."""
    folder = normalise_label(folder_label)
    if not folder or not labels:
        return False
    return any(token in folder or folder in token for token in labels)


def bank_is_registered(folder_label: str, tokens: frozenset[str]) -> bool:
    """Containment in either direction, matching `folder_agreement`'s matcher.

    Deliberately the same (deliberately imperfect) matcher: it is the reference
    the discovery report already uses, and an adjudication tool that disagreed
    with the report about which banks we support would be worse than one that
    is wrong in the same direction as the thing it is adjudicating.
    """
    folder = normalise_label(folder_label)
    if not folder:
        return False
    return any(token in folder or folder in token for token in tokens)
