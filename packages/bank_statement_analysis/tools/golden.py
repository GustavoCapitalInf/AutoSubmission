"""Golden responses: show that a change to the code leaves every statement and package output as it was.

Each side uploads every planned statement through one checkout's web API, in-process, into its own scratch data
folder, so the analysis runs with that checkout's code. Per statement it captures the served analysis and the JSON,
CSV and XLSX downloads; per package the package analysis and its three downloads; each under the default display
settings and under every setting flipped. Each shard mints its job and package ids from a fixed sequence, so two
sides that accept the same uploads mint the same ids (a package orders its documents by id); after an upload one side
refuses and the other accepts, the raw ids that follow differ. A response is kept as its status, content type,
disposition and body, with the job and package ids the tool minted replaced by tokens of their plan position and an
XLSX read part by part with its creation stamp masked; every other uuid stays as it is. Responses hold statement data:
the tool refuses an output path inside any repository, writes its files mode 600 and prints counts only.

  plan    --corpus DIR --out PLAN [--shards N]       one statement per PDF; packages of 2 to 6 from each bank folder;
                                                     N is 1 or more
  run     --plan PLAN --code PKG --work DIR [--ocr-from DIR]
                                                     ingest and capture every shard in parallel, one process each;
                                                     --ocr-from reuses another side's OCR readings only. The run
                                                     writes DIR/complete.json once each shard records one outcome
                                                     per planned statement, the packages its plan and outcomes call
                                                     for, and the eight responses of every accepted upload and
                                                     package; exit 1 when a shard fails, 2 when one captured none or
                                                     holds another inventory
  compare A B                                        counts by response kind, then each difference as its key; exit
                                                     0 when identical, 1 when a response differs, 2 when a side has
                                                     no valid complete.json, ran another plan, holds no responses, or
                                                     lost, changed or cannot read a manifest or a capture
  diff    A B --index KEY [KEY ...] --out FILE       the differing paths of those responses, every digit masked

What an identical compare does not cover: settings other than the defaults and all 14 flipped (2 of 2^14 mixes);
requests it does not capture (upload, status and settings responses, pages, markdown, md and html downloads,
package `?ids=` queries, the revenue review and reanalyze actions) and what a browser renders; OCR code, when a side
reuses another's readings with --ocr-from; and modes the environment sets, such as WITHHOLDING_DENOMINATOR_MODE and
RECONSTRUCTION_MODE, which the tool neither varies nor records.

Recipe, base checkout against your worktree (O a private folder outside every repository, PKG paths absolute):

  T=tools/golden.py; python -I $T plan --corpus "$BANK_STATEMENTS_DIR" --out $O/plan.json && python -I $T run --plan $O/plan.json --code $BASE_PKG --work $O/base && python -I $T run --plan $O/plan.json --code $HEAD_PKG --work $O/head --ocr-from $O/base && python -I $T compare $O/base $O/head
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import zipfile
import zlib
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import NoReturn

PROFILES = ("default", "flipped")
FORMATS = ("json", "csv", "xlsx")
KINDS = ("analysis", *FORMATS)
NO_PARSER = "no deterministic parser matched this statement"
OUTCOMES = ("analysed", "no matching parser", "not analysed", "failed", "upload refused")
RESPONSE_KEY = re.compile(r"[sp]\d{4,}\.(default|flipped)\.(analysis|json|csv|xlsx)")
UUID = re.compile(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
XLSX_STAMP = re.compile(r"<dcterms:created>[^<]*</dcterms:created>")
ABSENT = "<absent>"
DIFF_PATHS_PER_RESPONSE = 200
DIFFERENT, INCOMPLETE = 1, 2


def repository_of(path: Path) -> Path | None:
    """The repository a path would land in: the path itself or a folder above it holding a `.git` entry."""
    resolved = Path(path).resolve()
    for folder in (resolved, *resolved.parents):
        if os.path.lexists(folder / ".git"):
            return folder
    return None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_private(path: Path, data: bytes) -> None:
    """Write `data` to `path` with mode 600, an existing file's mode included."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def incomplete(reason: str) -> NoReturn:
    print(f"incomplete: {reason}", file=sys.stderr)
    raise SystemExit(INCOMPLETE)


def read_evidence(path: Path) -> bytes:
    """A file's bytes; exits INCOMPLETE when it is missing or unreadable."""
    try:
        return path.read_bytes()
    except OSError as error:
        incomplete(f"cannot read {path}: {error.strerror or type(error).__name__}")


def json_of(data: bytes) -> object:
    try:
        return json.loads(data)
    except ValueError:
        return None


def plan_of(plan_bytes: bytes) -> dict:
    """A plan parsed; exits INCOMPLETE unless it declares one or more shards."""
    planned = json_of(plan_bytes)
    if not isinstance(planned, dict) or type(planned.get("shards")) is not int or planned["shards"] < 1:
        incomplete("the plan is not JSON that declares one or more shards")
    return planned


def manifest_of(data: bytes, folder: Path) -> dict:
    """A shard's manifest parsed; exits INCOMPLETE unless it maps responses, statements and packages."""
    record = json_of(data)
    parts = [record.get(part) for part in ("responses", "statements", "packages")] if isinstance(record, dict) else []
    if not (parts and all(isinstance(part, dict) for part in parts)
            and all(RESPONSE_KEY.fullmatch(key) and isinstance(value, str) for key, value in parts[0].items())):
        incomplete(f"{folder}/manifest.json is not a shard manifest")
    return record


def positive(text: str) -> int:
    if (value := int(text)) < 1:
        raise argparse.ArgumentTypeError(f"{text} is not 1 or more")
    return value


def make_plan(files: list[tuple[str, int]], shards: int) -> dict:
    """Every (relative path, size) is a statement. The sorted statements of each top folder are cut into packages
    whose sizes cycle through 2 to 6; a last single statement stays out. Each package, and each statement outside
    one, goes whole to the shard with the fewest bytes so far, largest first."""
    folders: dict[str, list[tuple[str, int]]] = {}
    for relative, size in sorted(files):
        folders.setdefault(relative.split("/", 1)[0], []).append((relative, size))
    statements, packages, sizes = [], [], []
    for folder in sorted(folders):
        first = len(statements)
        for relative, size in folders[folder]:
            statements.append({"path": relative})
            sizes.append(size)
        start, end = first, len(statements)
        while end - start >= 2:
            count = min(2 + len(packages) % 5, end - start)
            packages.append({"members": list(range(start, start + count))})
            start += count
    packed = {member for package in packages for member in package["members"]}
    units = [package["members"] for package in packages] + [[i] for i in range(len(statements)) if i not in packed]
    load = [0] * shards
    for members in sorted(units, key=lambda members: (-sum(sizes[i] for i in members), members[0])):
        shard = load.index(min(load))
        load[shard] += sum(sizes[i] for i in members)
        for i in members:
            statements[i]["shard"] = shard
    for package in packages:
        package["shard"] = statements[package["members"][0]]["shard"]
    return {"shards": shards, "statements": statements, "packages": packages}


def xlsx_parts(data: bytes) -> list[list[str]]:
    """An XLSX as its [name, text] parts in order, the creation stamp in docProps/core.xml masked. The zip's own
    member times are left out with the rest of the container."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        parts = [[info.filename, archive.read(info).decode("utf-8", "surrogateescape")] for info in archive.infolist()]
    for part in parts:
        if part[0] == "docProps/core.xml":
            part[1] = XLSX_STAMP.sub("<dcterms:created>stamp</dcterms:created>", part[1])
    return parts


def canonical(status: int, content_type: str, disposition: str, body: bytes, ids: dict[bytes, bytes]) -> bytes:
    """A response as compared: a head line, the disposition line, then the body (an XLSX as its parts), with each id
    in `ids` (the job and package ids the tool minted) replaced by its plan position. Every other uuid stays."""
    if body.startswith(b"PK\x03\x04"):
        body = json.dumps(xlsx_parts(body)).encode()
    text = f"{status} {content_type}\n{disposition}\n".encode() + body
    return UUID.sub(lambda match: ids.get(match.group(), match.group()), text)


def response_kind(key: str) -> str:
    """`s0012.default.csv` -> `statement.default.csv`; `p0003.flipped.analysis` -> `package.flipped.analysis`."""
    index, profile, kind = key.split(".")
    return f"{'statement' if index[0] == 's' else 'package'}.{profile}.{kind}"


def compare_manifests(a: dict[str, str], b: dict[str, str]) -> tuple[dict[str, Counter], list[tuple[str, str]]]:
    """Per response kind, the count of each verdict; and every key that is not identical, with its verdict."""
    kinds: dict[str, Counter] = {}
    found = []
    for key in sorted(a.keys() | b.keys()):
        if key not in b:
            verdict = "only in A"
        elif key not in a:
            verdict = "only in B"
        else:
            verdict = "identical" if a[key] == b[key] else "different"
        kinds.setdefault(response_kind(key), Counter())[verdict] += 1
        if verdict != "identical":
            found.append((verdict, key))
    return kinds, found


def mask(value: object) -> str:
    return re.sub(r"\d", "#", value if isinstance(value, str) else json.dumps(value, sort_keys=True))


def parsed(key: str, data: bytes) -> object:
    """A canonical response as a tree: its two head lines, then a JSON body parsed, a CSV as rows of cells, an XLSX
    sheet as rows of cell markup and any other part or body as lines."""
    head, disposition, body = data.decode("utf-8", "surrogateescape").split("\n", 2)
    kind = key.rsplit(".", 1)[1]
    try:
        if kind == "csv":
            tree = list(csv.reader(io.StringIO(body, newline="")))
        elif kind == "xlsx":
            tree = {name: [re.findall(r"<c\b.*?</c>", row) for row in re.findall(r"<row\b.*?</row>", text)]
                    if "<row " in text else text.split("\n") for name, text in json.loads(body)}
        else:
            tree = json.loads(body)
    except (ValueError, csv.Error):
        tree = body.split("\n")
    return {"head": head, "disposition": disposition, "body": tree}


def differences(a: object, b: object, path: str = "") -> list[tuple[str, str, str]]:
    """Every path where two trees differ, with both values; keys and values have every digit masked. Lists are aligned
    first, so an element inserted or removed is one path; `[i:j]` names an element's place in A and in B, `-` where
    it is absent."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [found for key in sorted(a.keys() | b.keys())
                for found in differences(a.get(key, ABSENT), b.get(key, ABSENT), f"{path}/{mask(key)}")]
    if isinstance(a, list) and isinstance(b, list):
        found = []
        matcher = SequenceMatcher(None, [json.dumps(x, sort_keys=True) for x in a],
                                  [json.dumps(x, sort_keys=True) for x in b], autojunk=False)
        for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
            if tag == "equal":
                continue
            for step in range(max(a_end - a_start, b_end - b_start)):
                i, j = a_start + step, b_start + step
                found += differences(a[i] if i < a_end else ABSENT, b[j] if j < b_end else ABSENT,
                                     f"{path}[{i if i < a_end else '-'}:{j if j < b_end else '-'}]")
        return found
    return [] if a == b else [(path, mask(a), mask(b))]


def plan(args) -> None:
    corpus = Path(args.corpus).resolve()
    files = [(path.relative_to(corpus).as_posix(), path.stat().st_size) for path in corpus.rglob("*")
             if path.is_file() and path.suffix.lower() == ".pdf"]
    planned = make_plan(files, args.shards)
    planned["corpus"] = str(corpus)
    write_private(Path(args.out), json.dumps(planned).encode())
    sizes = Counter(len(package["members"]) for package in planned["packages"])
    print(f"statements {len(planned['statements'])}, packages {len(planned['packages'])} "
          f"(sizes {dict(sorted(sizes.items()))}), shards {args.shards}")


def load_app(code: Path, data: Path):
    os.environ["WEBAPP_DATA_DIR"] = str(data)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ.pop("WEBAPP_AUTH_PASSWORD", None)
    os.chdir(code)
    sys.path.insert(0, str(code))
    import webapp.app as app_module
    from analysis import display_settings
    for module in (app_module, display_settings):
        if not Path(module.__file__).resolve().is_relative_to(code):
            raise SystemExit(f"refused: imported {module.__name__} from outside {code}")
    return app_module, display_settings.DEFAULTS


def repeatable_ids(seed: str) -> None:
    """Make the ids minted on this thread, where the test client runs every request, repeat from run to run. A
    package's output follows its job ids' order (its document lists are sorted by id), so random ids would order the
    two sides differently. Ids the worker thread mints stay random."""
    random_uuid4, minted = uuid.uuid4, itertools.count()

    def uuid4() -> uuid.UUID:
        if threading.current_thread() is not threading.main_thread():
            return random_uuid4()
        return uuid.UUID(bytes=hashlib.sha256(f"{seed}/{next(minted)}".encode()).digest()[:16], version=4)

    uuid.uuid4 = uuid4


def outcome(status: dict | None) -> str:
    if status is None:
        return "upload refused"
    if status["status"] != "done":
        return "failed"
    if status["analysis_ready"]:
        return "analysed"
    return "no matching parser" if status["analysis_error"] == NO_PARSER else "not analysed"


def shard(args) -> None:
    os.umask(0o077)
    # MuPDF prints a PDF's parse errors on standard output; only the counts below may reach it.
    report = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    planned = plan_of(read_evidence(Path(args.plan)))
    corpus, work, k = Path(planned["corpus"]), Path(args.work), args.shard
    data, out = work / "data" / f"shard{k}", work / "capture" / f"shard{k}"
    data.mkdir(parents=True)
    out.mkdir(parents=True)
    app_module, defaults = load_app(Path(args.code).resolve(), data)
    repeatable_ids(f"shard{k}")
    cache, client = app_module.store.cache, app_module.app.test_client()
    seeded = 0
    if args.ocr_from:
        for path in sorted((Path(args.ocr_from) / "data" / f"shard{k}" / "artifacts" / "ocr").glob("*/*.json")):
            payload = json.loads(path.read_text())
            cache.put("ocr", payload["input_sha256"], payload["settings_key"], payload["artifact"])
            seeded += 1
    started = time.monotonic()
    jobs = {}
    for index, statement in enumerate(planned["statements"]):
        if statement["shard"] == k:
            with open(corpus / statement["path"], "rb") as stream:
                response = client.post("/upload", data={"files": (stream, Path(statement["path"]).name)})
            if response.status_code == 200:
                jobs[index] = response.get_json()["jobs"][0]["id"]
    statuses = {}
    while len(statuses) < len(jobs):
        time.sleep(1)
        for index in jobs.keys() - statuses.keys():
            status = client.get(f"/status/{jobs[index]}").get_json()
            if status["status"] not in ("queued", "processing"):
                statuses[index] = status
    outcomes = {index: outcome(statuses.get(index))
                for index, statement in enumerate(planned["statements"]) if statement["shard"] == k}
    packages, analysed_members = {}, {}
    for index, package in enumerate(planned["packages"]):
        members = [jobs[member] for member in package["members"] if member in jobs]
        if package["shard"] == k and len(members) >= 2:
            packages[index] = client.post("/package", json={"ids": members}).get_json()["package_id"]
            analysed_members[index] = sum(outcomes[member] == "analysed" for member in package["members"])
    ingested = time.monotonic()
    ids = {job.encode(): f"job-{index:04d}".encode() for index, job in jobs.items()}
    ids.update({package.encode(): f"package-{index:04d}".encode() for index, package in packages.items()})
    urls = {}
    for index, job in jobs.items():
        urls[f"s{index:04d}"] = {"analysis": f"/analysis/{job}", **{fmt: f"/download/{job}/{fmt}" for fmt in FORMATS}}
    for index, package in packages.items():
        query = f"package_id={package}"
        urls[f"p{index:04d}"] = {"analysis": f"/package_analysis?{query}",
                                 **{fmt: f"/package_download/{fmt}?{query}" for fmt in FORMATS}}
    manifest = {}
    for profile in PROFILES:
        settings = dict(defaults) if profile == "default" else {key: not value for key, value in defaults.items()}
        if client.post("/api/settings", json=settings).status_code != 200:
            raise SystemExit(f"refused: the {profile} settings were not saved")
        for name, routes in urls.items():
            for kind, url in routes.items():
                response = client.get(url)
                data_bytes = canonical(response.status_code, response.content_type,
                                       response.headers.get("Content-Disposition", ""), response.get_data(), ids)
                key = f"{name}.{profile}.{kind}"
                write_private(out / f"{key}.gz", gzip.compress(data_bytes, mtime=0))
                manifest[key] = digest(data_bytes)
    record = {"responses": manifest, "statements": outcomes, "packages": analysed_members}
    write_private(out / "manifest.json", json.dumps(record, sort_keys=True).encode())
    stages = {stage: f"{row['entries']} entries, {row['hits']} hits" for stage, row in sorted(cache.stats().items())}
    print(f"shard {k}: statements {len(outcomes)}, packages {len(packages)}, responses {len(manifest)}; "
          f"ocr seeded {seeded}; cache {stages}; ingest {ingested - started:.0f} s, "
          f"capture {time.monotonic() - ingested:.0f} s", file=report)


def run(args) -> None:
    plan_bytes = read_evidence(Path(args.plan))
    shards = plan_of(plan_bytes)["shards"]
    work = Path(args.work)
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit(f"refused: {work} is not empty; name a new folder")
    (work / "logs").mkdir(mode=0o700)
    started = time.monotonic()
    command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "shard", "--plan", str(Path(args.plan)),
               "--code", str(Path(args.code).resolve()), "--work", str(work.resolve())]
    if args.ocr_from:
        command += ["--ocr-from", str(Path(args.ocr_from).resolve())]
    running = []
    for k in range(shards):
        log = os.open(work / "logs" / f"shard{k}.err", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        running.append(subprocess.Popen([*command, "--shard", str(k)], stdout=subprocess.PIPE, stderr=log, text=True))
        os.close(log)
    failed = 0
    for k, process in enumerate(running):
        print(process.communicate()[0].strip() or f"shard {k}: no report")
        failed += process.returncode != 0
    print(f"wall {time.monotonic() - started:.0f} s; shards failed {failed} (their stderr is in {work / 'logs'})")
    if failed:
        raise SystemExit(1)
    print(f"complete: {seal(work, plan_bytes)} responses")


def seal(work: Path, plan_bytes: bytes) -> int:
    """Write `complete.json`, which compare requires: the plan's digest and, per planned shard, its counts and its
    manifest's digest. Exits INCOMPLETE, writing nothing, unless every shard records one known outcome for each of its
    planned statements and nothing else, the packages of its plan with two or more accepted uploads (each with its
    count of analysed members), and the eight responses of each accepted upload and package, at least one. Returns the
    number of responses."""
    planned = plan_of(plan_bytes)
    shards = []
    for k in range(planned["shards"]):
        folder = work / "capture" / f"shard{k}"
        manifest = read_evidence(folder / "manifest.json")
        record = manifest_of(manifest, folder)
        outcomes = record["statements"]
        statements = {str(i) for i, statement in enumerate(planned["statements"]) if statement["shard"] == k}
        if outcomes.keys() != statements or not set(outcomes.values()) <= set(OUTCOMES):
            incomplete(f"shard {k} records {len(outcomes)} outcomes, not one for each of its {len(statements)} "
                       f"planned statements")
        accepted = {int(i) for i, done in outcomes.items() if done != "upload refused"}
        packages = {str(i): sum(outcomes.get(str(member)) == "analysed" for member in package["members"])
                    for i, package in enumerate(planned["packages"])
                    if package["shard"] == k and len(accepted & set(package["members"])) >= 2}
        if record["packages"] != packages:
            incomplete(f"shard {k} records {len(record['packages'])} packages, its plan and outcomes call for "
                       f"{len(packages)}")
        names = [f"s{i:04d}" for i in accepted] + [f"p{int(i):04d}" for i in packages]
        expected = {f"{name}.{profile}.{kind}" for name in names for profile in PROFILES for kind in KINDS}
        if not expected:
            incomplete(f"shard {k} captured no responses; no upload was accepted")
        if record["responses"].keys() != expected:
            incomplete(f"shard {k} holds {len(record['responses'])} responses, its outcomes call for {len(expected)}")
        shards.append({"manifest": digest(manifest), "statements": len(outcomes), "packages": len(packages),
                       "responses": len(expected)})
    write_private(work / "complete.json", json.dumps({"plan": digest(plan_bytes), "shards": shards}).encode())
    return sum(shard["responses"] for shard in shards)


def unpacked(capture: Path) -> bytes | None:
    """A capture's canonical bytes; None when the file is missing or not one whole gzip stream."""
    try:
        return gzip.decompress(capture.read_bytes())
    except (OSError, EOFError, zlib.error):
        return None


def load_side(work: Path) -> dict:
    """A finished run's manifests, merged, once its completion marker vouches for each shard's manifest and each
    capture's bytes match their manifest hash. Anything less, or a shard with no responses, exits INCOMPLETE."""
    try:
        marker = json.loads((work / "complete.json").read_bytes())
    except (OSError, ValueError):
        incomplete(f"{work} holds no readable complete.json; its run did not finish")
    shards = marker.get("shards") if isinstance(marker, dict) else None
    if not (isinstance(shards, list) and shards and isinstance(marker.get("plan"), str)
            and all(isinstance(sealed, dict) and isinstance(sealed.get("manifest"), str) for sealed in shards)):
        incomplete(f"{work}/complete.json does not name a plan and one or more sealed shards")
    side: dict = {"plan": marker["plan"], "responses": {}, "statements": {}, "packages": {}}
    for k, sealed in enumerate(shards):
        folder = work / "capture" / f"shard{k}"
        manifest = read_evidence(folder / "manifest.json")
        if digest(manifest) != sealed["manifest"]:
            incomplete(f"{folder} lost its manifest or it changed since its run")
        record = manifest_of(manifest, folder)
        if not record["responses"]:
            incomplete(f"{folder} holds no responses")
        for key, expected in record["responses"].items():
            if (data := unpacked(folder / f"{key}.gz")) is None or digest(data) != expected:
                incomplete(f"{folder} lost the capture {key} or it no longer matches its manifest")
        for part in ("responses", "statements", "packages"):
            side[part].update(record[part])
    return side


def compare(args) -> None:
    sides = {"A": load_side(Path(args.a)), "B": load_side(Path(args.b))}
    if sides["A"]["plan"] != sides["B"]["plan"]:
        incomplete("the two sides ran different plans")
    for name, side in sides.items():
        outcomes = Counter(side["statements"].values())
        analysed = sum(count >= 2 for count in side["packages"].values())
        print(f"coverage {name}: statements {sum(outcomes.values())} {dict(sorted(outcomes.items()))}; "
              f"packages {len(side['packages'])}, with two or more analysed members {analysed}")
    kinds, found = compare_manifests(sides["A"]["responses"], sides["B"]["responses"])
    print("responses:", dict(sorted(sum(kinds.values(), Counter()).items())))
    for kind in sorted(kinds):
        print(f"  {kind:26s} {dict(sorted(kinds[kind].items()))}")
    for verdict, key in found:
        print(f"{verdict} {key}")
    if found:
        raise SystemExit(DIFFERENT)


def stored(work: str, key: str) -> bytes:
    path = next((Path(work) / "capture").glob(f"shard*/{key}.gz"), None)
    if path is None or (data := unpacked(path)) is None:
        incomplete(f"{work} holds no readable response {key}")
    return data


def diff(args) -> None:
    report = []
    for key in args.index:
        a, b = stored(args.a, key), stored(args.b, key)
        found = differences(parsed(key, a), parsed(key, b))
        note = "; the bytes differ in order or layout" if a != b and not found else ""
        line = f"{key}: {len(found)} differing paths{note}"
        report += [f"== {line}", *("\t".join(row) for row in found[:DIFF_PATHS_PER_RESPONSE])]
        print(line)
    write_private(Path(args.out), ("\n".join(report) + "\n").encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("plan")
    p.add_argument("--corpus", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--shards", type=positive, default=16)
    for name in ("run", "shard"):
        p = commands.add_parser(name)
        p.add_argument("--plan", required=True)
        p.add_argument("--code", required=True)
        p.add_argument("--work", required=True)
        p.add_argument("--ocr-from")
        if name == "shard":
            p.add_argument("--shard", type=int, required=True)
    p = commands.add_parser("compare")
    p.add_argument("a")
    p.add_argument("b")
    p = commands.add_parser("diff")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--index", nargs="+", required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args()
    for path in (getattr(args, "out", None), getattr(args, "work", None)):
        if path and (repository := repository_of(Path(path))):
            raise SystemExit(f"refused: {path} is inside the repository at {repository}; responses hold statement data")
    {"plan": plan, "run": run, "shard": shard, "compare": compare, "diff": diff}[args.command](args)


if __name__ == "__main__":
    main()
