"""The registry fingerprint, and the analysis cache key that now carries it (W3 §REGFP).

Before this, `analysis_settings_key` fingerprinted the stage version, the parse
mode and three `analysis.config` knobs, and the 72-entry parser registry was
invisible to it. Register a parser, drop one, rewire a `parse`, add a
`supersedes` edge — the key did not move, and every document the change affects
kept being served its pre-change analysis out of the cache. What stood between
that and a wrong published answer was the composed `ANALYSIS_STAGE_VERSION` bump
this programme performs at each train: a policy someone must remember, not a
construction. These tests hold the construction.

Two of them are the guards the card names: a registration added to a scratch
registry MOVES the key, and the key is byte-identical across two fresh
processes on the unchanged registry. The rest fence the material — every
declared field partitions, and a marker's test BODY does not, because code is
the stage version's job and a digest that pretended otherwise would be lying
about what it covers.
"""
from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401  (populates the registry)
from analysis.schema import Statement
from webapp.artifact_cache import analysis_settings_key, text_sha256

ROOT = Path(__file__).resolve().parents[1]


def parse_nothing(markdown: str) -> Statement | None:
    """A module-level parse for synthetic registrations.

    Named rather than a lambda on purpose: `_declared_callable` records
    `module.qualname`, and two lambdas in one module share `<lambda>`. A test
    about precision must not be written with the one shape that is imprecise.
    """
    return None


def parse_something(markdown: str) -> Statement | None:
    return Statement(bank="Synthetic")


def normalize_upper(text: str) -> str:
    return text.upper()


def normalize_lower(text: str) -> str:
    return text.lower()


def no_contradictions(markdown: str, statement: Statement) -> list[str]:
    return []


def also_no_contradictions(markdown: str, statement: Statement) -> list[str]:
    return []


def contains(needle: str):
    return lambda markdown: needle in markdown


@pytest.fixture
def scratch_registry():
    """An empty registry that leaves the real one exactly as it was.

    The same save/restore `tests/test_parser_registry.py` uses. It matters more
    here than there: these tests read a digest OVER the registry, so a leaked
    synthetic registration would move `analysis_settings_key` for every test
    that runs afterwards.
    """
    saved = dict(pr._REGISTRY)
    pr.clear_registry()
    try:
        yield
    finally:
        pr.clear_registry()
        pr._REGISTRY.update(saved)


def make(parser_id: str, **changes) -> pr.Registration:
    fields = {
        "id": parser_id,
        "bank": parser_id.replace("_", " ").title(),
        "markers": (pr.required("m", contains("BANK")),),
        "parse": parse_nothing,
    }
    fields.update(changes)
    return pr.register(pr.Registration(**fields))


# ---------------------------------------------------------------------------
# the two guards the card names
# ---------------------------------------------------------------------------


def test_a_new_registration_moves_the_analysis_settings_key(scratch_registry):
    """GUARD 1. The reason the card exists: a registration the analysis stage
    would dispatch on must be a registration the cache key can see."""
    make("first")
    before = analysis_settings_key(parse_mode="deterministic")

    make("second")
    after = analysis_settings_key(parse_mode="deterministic")
    assert after != before, "adding a registration left the analysis cache key unmoved"

    # And it is a pure function of the registry, not a counter: removing the
    # registration again returns the byte-identical key, so a reverted merge
    # re-reaches the artifacts it wrote rather than orphaning them.
    del pr._REGISTRY["second"]
    assert analysis_settings_key(parse_mode="deterministic") == before


def test_the_key_is_byte_identical_across_two_fresh_processes():
    """GUARD 2. The key must be a function of the registry DATA and nothing
    else — not of dict insertion order, not of `frozenset` iteration order,
    not of any `id()`. `PYTHONHASHSEED` is the lever that exposes all three:
    string hashing is randomized per process by default, so a digest that
    depended on a set's or a dict's iteration order would differ between these
    two runs and the archive's analysis cache would rotate on every restart.
    """
    code = (
        "from webapp.artifact_cache import analysis_settings_key;"
        "from analysis.parser_registry import registry_fingerprint;"
        "print(registry_fingerprint());"
        "print(analysis_settings_key(parse_mode='deterministic'))"
    )
    runs = []
    for seed in ("0", "1"):
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=ROOT,
            # The parent environment, plus the seed. NOT a scrubbed one: the
            # analysis knobs are in this key too, so a child that could not see
            # an `ANALYSIS_MODEL` its parent can would fail this test for a
            # reason that has nothing to do with the registry.
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        assert result.returncode == 0, result.stderr
        runs.append(result.stdout.strip().splitlines())

    assert runs[0] == runs[1], f"key moved between processes: {runs}"
    # …and it is the key THIS process computes, so the subprocesses are not
    # merely agreeing with each other about something wrong.
    assert runs[0] == [
        pr.registry_fingerprint(),
        analysis_settings_key(parse_mode="deterministic"),
    ]


# ---------------------------------------------------------------------------
# the fingerprint is wired into the key, and derived in ONE place
# ---------------------------------------------------------------------------


def test_the_analysis_settings_key_reads_the_registry_fingerprint(monkeypatch):
    """The key must consult the shared helper, not a copy of its logic."""
    import webapp.artifact_cache as module

    before = analysis_settings_key()
    monkeypatch.setattr(module, "registry_fingerprint", lambda: "A" * 64)
    assert analysis_settings_key() != before


def test_the_generic_structurer_flag_partitions_the_analysis_key(monkeypatch):
    """The W3-3c generic rung changes the published payload of every unclaimed
    document — it publishes a statement where the pipeline would otherwise
    refuse — so its switch must partition the analysis key: two runs of the
    same archive, one with the rung and one without, must never share an
    analysis entry.

    P22-IDENTITY (Phase 2.2, D6) moved that switch from the environment
    variable `GENERIC_STRUCTURER_ENABLED` to `Settings.reconstruction_mode`
    (`RECONSTRUCTION_MODE`, closed vocabulary `off | research | production`)
    and RETIRED the variable. This pin follows the contract: the setting
    partitions the key and the rung reads it; the retired variable does
    neither, in any value that used to switch the rung on. Off is the
    default and the archive's whole history, so nothing cached today was
    written under any other value.
    """
    from analysis.config import RECONSTRUCTION_MODE_ENV, Settings
    from analysis.structurer import STRUCTURER_ENV, structurer_enabled

    monkeypatch.delenv(STRUCTURER_ENV, raising=False)
    monkeypatch.delenv(RECONSTRUCTION_MODE_ENV, raising=False)
    assert structurer_enabled() is False
    off = analysis_settings_key(parse_mode="deterministic")

    # the retired variable is INERT: no value moves the rung or the key
    for value in ("1", "true", "yes", "0", "", "  ", "false", "no"):
        monkeypatch.setenv(STRUCTURER_ENV, value)
        assert structurer_enabled() is False, value
        assert analysis_settings_key(parse_mode="deterministic") == off, value
    monkeypatch.delenv(STRUCTURER_ENV, raising=False)

    # the setting partitions the key, and the key reads the structurer's own
    # accessor, so it agrees with the rung about what "enabled" MEANS
    monkeypatch.setenv(RECONSTRUCTION_MODE_ENV, "research")
    assert structurer_enabled() is True
    research = analysis_settings_key(parse_mode="deterministic")
    assert research != off
    monkeypatch.setenv(RECONSTRUCTION_MODE_ENV, "production")
    assert structurer_enabled() is True
    production = analysis_settings_key(parse_mode="deterministic")
    assert production not in (off, research)
    for value in ("off", "", "  "):
        monkeypatch.setenv(RECONSTRUCTION_MODE_ENV, value)
        assert structurer_enabled() is False, repr(value)
        assert analysis_settings_key(parse_mode="deterministic") == off, repr(value)

    # and through an explicit settings object, independently of the environment
    monkeypatch.delenv(RECONSTRUCTION_MODE_ENV, raising=False)
    monkeypatch.setenv(STRUCTURER_ENV, "1")
    explicit_off = Settings(api_key="", model="m", escalation_model="e")
    explicit_on = Settings(api_key="", model="m", escalation_model="e", reconstruction_mode="research")
    assert structurer_enabled(explicit_off) is False and structurer_enabled(explicit_on) is True
    assert analysis_settings_key(parse_mode="deterministic", analysis_settings=explicit_off) != \
        analysis_settings_key(parse_mode="deterministic", analysis_settings=explicit_on)


def test_the_digest_uses_the_caches_own_hashing_convention():
    """`analysis` cannot import `webapp` — the dependency runs the other way —
    so `registry_fingerprint` reproduces the cache's canonical-JSON + UPPER-hex
    SHA-256 convention in three lines. This is what stops the two from drifting
    apart while both look correct in isolation."""
    canonical = json.dumps(
        pr.registry_key_material(), sort_keys=True, separators=(",", ":")
    )
    assert pr.registry_fingerprint() == text_sha256(canonical)


def test_the_material_is_the_registry_in_dispatch_order():
    material = pr.registry_key_material()
    assert material["material_version"] == pr.REGISTRY_MATERIAL_VERSION
    assert [entry["id"] for entry in material["registrations"]] == [
        registration.id for registration in pr.registrations()
    ]


#: A THREE-registration registry whose one edge set has TWO members, built in a
#: fresh process and reported as both the material's list and the digest.
#:
#: Two members is the whole point. Every `supersedes` set the registry ships
#: today holds exactly one id, and a one-element set has one iteration order, so
#: the shipped registry cannot tell `sorted(...)` apart from `list(...)` — an
#: assertion over it is a tautology and the mutation survives it. `frozenset`
#: iteration order for `{"a", "b"}` IS seed-dependent (measured: `['a', 'b']`
#: under PYTHONHASHSEED 0 and 1, `['b', 'a']` under 2, 3 and 4), which is what
#: makes the seeds below a real experiment rather than a repeated one.
_MULTI_EDGE_CODE = """
import analysis.parser_registry as pr


def make(parser_id, supersedes=frozenset()):
    pr.register(pr.Registration(
        id=parser_id,
        bank=parser_id.upper(),
        markers=(pr.required("m", str.isupper),),
        parse=str.strip,
        supersedes=supersedes,
    ))


make("a")
make("b")
make("subject", frozenset({"a", "b"}))
entry = {e["id"]: e for e in pr.registry_key_material()["registrations"]}["subject"]
print(entry["supersedes"])
print(pr.registry_fingerprint())
"""


def test_supersedes_edges_are_hashed_sorted(scratch_registry):
    """A `frozenset` iterates in hash order, which is per-process.

    Asserted on a TWO-member edge set, because the shipped registry's are all
    one member and prove nothing about the sort. In-process this assertion is
    only half a guard — this process has one seed, and under half of them
    `list()` and `sorted()` agree — so the deterministic kill is the
    cross-seed test below.
    """
    make("a")
    make("b")
    make("subject", supersedes=frozenset({"a", "b"}))
    entries = {entry["id"]: entry for entry in pr.registry_key_material()["registrations"]}
    assert entries["subject"]["supersedes"] == ["a", "b"]


def test_a_two_member_edge_set_hashes_identically_across_hash_seeds():
    """GUARD 2b — the sort in the material, held by four fresh processes.

    Four seeds, not two: `['a', 'b']` comes out of PYTHONHASHSEED 0 and 1 and
    `['b', 'a']` out of 2, 3 and 4, so a two-seed experiment can agree by
    accident. With 0-3 an unsorted digest is guaranteed to disagree with
    itself, and that is what makes `sorted(registration.supersedes)`
    mutation-killable rather than merely correct-looking.
    """
    runs = []
    for seed in ("0", "1", "2", "3"):
        result = subprocess.run(
            [sys.executable, "-c", _MULTI_EDGE_CODE],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        assert result.returncode == 0, result.stderr
        runs.append((seed, result.stdout.strip().splitlines()))

    edge_lines = {lines[0] for _, lines in runs}
    digests = {lines[1] for _, lines in runs}
    assert len(digests) == 1, f"the digest moved with the hash seed: {runs}"
    assert edge_lines == {"['a', 'b']"}, f"edge order leaked into the material: {runs}"


# ---------------------------------------------------------------------------
# what the material covers …
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"bank": "Renamed Bank"}, id="bank"),
        pytest.param({"band": 10}, id="band"),
        pytest.param({"supersedes": frozenset({"other"})}, id="supersedes"),
        pytest.param({"markers": (pr.required("renamed", contains("BANK")),)}, id="marker_id"),
        pytest.param({"markers": (pr.corroborating("m", contains("BANK")),)}, id="marker_kind"),
        pytest.param(
            {"markers": (pr.required("m", contains("BANK")), pr.required("m2", contains("X")))},
            id="marker_added",
        ),
        pytest.param({"parse": parse_something}, id="parse"),
        pytest.param({"normalize": normalize_upper}, id="normalize"),
        pytest.param({"formal_statement": False}, id="formal_statement"),
        pytest.param({"informal_quality_note": "note"}, id="informal_quality_note"),
        pytest.param({"informal_integrity_note": "note"}, id="informal_integrity_note"),
        pytest.param({"integrity_checks": (no_contradictions,)}, id="integrity_checks"),
    ],
)
def test_every_declared_field_partitions_the_fingerprint(scratch_registry, changes):
    """Each field, on its own, with everything else held still. A field that
    reaches the published payload but not the digest is a stale-artifact class
    nobody would find until a document came back wrong."""
    make("other")  # so the `supersedes` case has a real target to point at
    make("subject")
    before = pr.registry_fingerprint()

    pr._REGISTRY["subject"] = pr.with_overrides(pr._REGISTRY["subject"], **changes)
    assert pr.registry_fingerprint() != before, f"{changes} did not move the digest"


def test_swapping_two_integrity_checks_moves_the_fingerprint(scratch_registry):
    """Two checks with identical behaviour are still two different declared
    names, and which ones a registration runs is what the digest is recording."""
    make("subject", integrity_checks=(no_contradictions,))
    before = pr.registry_fingerprint()
    pr._REGISTRY["subject"] = pr.with_overrides(
        pr._REGISTRY["subject"], integrity_checks=(also_no_contradictions,)
    )
    assert pr.registry_fingerprint() != before


def test_removing_a_registration_moves_the_fingerprint(scratch_registry):
    make("first")
    make("second")
    before = pr.registry_fingerprint()
    del pr._REGISTRY["second"]
    assert pr.registry_fingerprint() != before


def test_an_empty_registry_is_a_distinct_honest_partition(scratch_registry):
    """Not an error: a process that analyses with no parsers loaded produces
    real (unclaimed) answers, and they belong under their own key rather than
    colliding with the 72-registration run's."""
    empty = pr.registry_fingerprint()
    make("first")
    assert pr.registry_fingerprint() != empty


def test_registration_insertion_order_does_not_move_the_fingerprint():
    """Dispatch order is `(band, id)` over the data, so the digest must be too.
    Otherwise reordering the entries table — which changes nothing about
    dispatch — would rotate the whole analysis cache."""
    saved = dict(pr._REGISTRY)
    try:
        pr.clear_registry()
        make("alpha")
        make("beta")
        forwards = pr.registry_fingerprint()

        pr.clear_registry()
        make("beta")
        make("alpha")
        assert pr.registry_fingerprint() == forwards
    finally:
        pr.clear_registry()
        pr._REGISTRY.update(saved)


# ---------------------------------------------------------------------------
# … and what it deliberately does not
# ---------------------------------------------------------------------------


def test_a_markers_test_body_is_not_key_material(scratch_registry):
    """The code/data boundary, asserted rather than described.

    Same marker id, same kind, a test that matches something else entirely: the
    digest does not move, because hashing behaviour is the stage version's job
    and this digest does not claim to do it. Stated as a test so that a future
    attempt to widen the material has to argue with a failing assertion instead
    of a paragraph.
    """
    make("subject", markers=(pr.required("m", contains("BANK")),))
    before = pr.registry_fingerprint()
    pr._REGISTRY["subject"] = pr.with_overrides(
        pr._REGISTRY["subject"], markers=(pr.required("m", contains("SOMETHING ELSE")),)
    )
    assert pr.registry_fingerprint() == before


# ---------------------------------------------------------------------------
# callable identity
# ---------------------------------------------------------------------------


def test_the_production_registry_declares_only_nameable_callables():
    """Every registered callable resolves to a real `module.qualname`.

    This is what makes the digest PRECISE on the registry that ships: a
    `functools.partial` is refused outright (below), but a lambda would be
    accepted and every lambda in a module shares `<lambda>`, so rewiring one
    parse to another would be invisible. None are registered today.
    """
    for registration in pr.registrations():
        callables = [("parse", registration.parse)]
        if registration.normalize is not None:
            callables.append(("normalize", registration.normalize))
        callables += [
            (f"integrity_checks[{index}]", check)
            for index, check in enumerate(registration.integrity_checks)
        ]
        for field_name, fn in callables:
            name = pr._declared_callable(registration.id, field_name, fn)
            assert "<" not in name, f"{registration.id}.{field_name} is unnameable: {name}"
            assert name.count(".") >= 1, f"{registration.id}.{field_name} has no module: {name}"


def test_an_unnameable_callable_is_refused_when_the_registry_is_validated(scratch_registry):
    """A `functools.partial` has no `__qualname__`, and reducing it to its TYPE
    would give every partial in the process the same name — a rewiring that
    left the digest unmoved.

    It is refused by `validate_registry`, which is what `load()` runs over the
    entries table, so an unnameable callable cannot reach production at all.
    Before this it surfaced only from `analysis_settings_key`, which meant the
    first caller to derive a cache key discovered somebody else's registration
    mistake — and made a function that had been total able to raise.
    """
    make("subject", parse=functools.partial(parse_nothing))
    with pytest.raises(TypeError) as excinfo:
        pr.validate_registry()
    assert "subject.parse" in str(excinfo.value)
    assert "__qualname__" in str(excinfo.value)


def test_the_shipped_registry_validates():
    """The production entries table passes the check that now runs inside
    `validate_registry` — stated separately from the 72-way sweep below so a
    regression names the mechanism rather than the census."""
    pr.validate_registry()


def test_band_is_hashed_as_declared(scratch_registry):
    """`sort_key` uses `band` as declared, so `100.9` orders differently from
    `100` and must hash differently. An `int()` coercion in the material would
    have made the two collide — the digest saying "unchanged" about a registry
    whose dispatch order had moved."""
    make("subject", band=100)
    before = pr.registry_fingerprint()
    pr._REGISTRY["subject"] = pr.with_overrides(pr._REGISTRY["subject"], band=100.9)
    assert pr.registry_fingerprint() != before


# ---------------------------------------------------------------------------
# the self-load: the join's process must reach the same key
# ---------------------------------------------------------------------------


def test_the_fingerprint_loads_the_registry_when_nothing_else_has():
    """A process that computes the key without importing the parsers must not
    get the empty-registry digest — that is telemetry's process, and the
    mismatch would be invisible (`REASON_PAYLOAD_ABSENT` on every row, an
    instrument reporting nothing wrong while measuring nothing)."""
    code = (
        "import sys;"
        "from webapp.artifact_cache import analysis_settings_key;"
        "assert 'analysis.parser_registry_entries' not in sys.modules;"
        "key = analysis_settings_key(parse_mode='deterministic');"
        "import analysis.parser_registry as pr;"
        "print(len(pr.registrations()));"
        "print(key)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0, result.stderr
    loaded, key = result.stdout.strip().splitlines()
    assert int(loaded) == len(pr.registrations())
    assert key == analysis_settings_key(parse_mode="deterministic")


def test_a_cleared_registry_is_not_resurrected_by_the_fingerprint(scratch_registry):
    """The other half of the self-load, and the reason it is guarded on
    `_REGISTRY` being empty rather than on a flag: a test that cleared the
    registry has already imported the entries module, so the import inside
    `_ensure_registry_loaded` is a no-op and cannot put the 72 real
    registrations back underneath it."""
    make("only")
    assert [registration.id for registration in pr.registrations()] == ["only"]
    pr.registry_fingerprint()
    assert [registration.id for registration in pr.registrations()] == ["only"]
