"""Research dataset gate: identity before computation.

GOVERNANCE TOOLING ONLY. It computes no economic quantity, reads no Clean OOS
data, records no dataset use, and imports nothing from the money path. It
exists so that a future registered experiment cannot silently run against a
different, incomplete or temporary copy of its data.

WHY IT IS NEEDED (docs/2026-09-23-research-reproducibility-audit.md). Research
runners have located their price data by globbing Claude session scratchpads
in the OS temp directory, taking the first match, accepting a folder with as
few as 200 of 230 files, and skipping unreadable files silently. None of that
could tell two datasets apart.

WHAT IT PROVIDES
  verify_dataset(id)        verify a registered dataset's durable copy against
                            its checksum list - exact file set, every SHA-256,
                            and the dataset-level hash - and return its path.
                            Refuses a lost dataset and any copy under a
                            temporary directory.
  check_registration(h)     list what a hypothesis is missing before it may be
                            registered: dataset ID and SHA-256 (in
                            `parameters["dataset"]`), population and benchmark
                            (in `parameters`), information boundary and
                            execution assumptions (existing fields).
  audit()                   verify every preserved dataset and report every
                            registration dated on or after the effective date
                            that lacks the required identity.
  price_dir(folder)         what runners call: "deep" -> the verified decade
                            directory; "long" -> refused (the thirty-year data
                            is lost). `decade_dir()` is price_dir("deep").
  dataset_file(dir, name)   one file of a verified directory, or an error.
  unpreserved_intraday_store(p)
                            the ONE sanctioned scratchpad lookup, for the listed
                            intraday stores that have no verified copy. Not a
                            governed dataset; never returns decade data.

It reuses what exists. `Hypothesis.parameters` is already a sealed free-form
dict and `information_boundary` / `execution_assumptions` are already sealed
fields, so no registration schema changes. Dataset identities live in
`docs/datasets/registry.json`, next to their manifests.

THE RULE (docs/datasets/README.md): from 2026-09-24, a registration must name
a registered dataset ID and SHA-256, and its runner must call
`verify_dataset` - and load bars only from the path it returns - before
computing any result. Registrations before that date are grandfathered and
listed, not failed.

Usage:
  python scripts/research_gate.py --audit
  python scripts/research_gate.py --verify decade-2016-2026-split-adjusted-230
"""

import glob
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "docs" / "datasets" / "registry.json"
PREREG = REPO / "docs" / "preregistrations.jsonl"
RESEARCH_ROOT = REPO / "data" / "research"


class DatasetGateError(RuntimeError):
    """The data a computation would use cannot be shown to be the data it names."""


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_checksums(path):
    """A standard `sha256sum` list: '<sha256>  <file>' per line."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        if name in out:
            raise DatasetGateError("checksum list names {0} twice".format(name))
        out[name] = digest
    return out


def dataset_hash(entries):
    """The dataset-level identity: SHA-256 of '<file>\\t<size>\\t<sha256>\\n'
    per file, sorted by file name. Must match docs/datasets manifests."""
    text = "".join("{0}\t{1}\t{2}\n".format(n, size, digest)
                   for n, (size, digest) in sorted(entries.items()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _under_temp(path):
    p = str(Path(path).resolve()).replace("\\", "/").lower()
    temp = str(Path(tempfile.gettempdir()).resolve()).replace("\\", "/").lower()
    return p.startswith(temp) or "/temp/claude/" in p or "/scratchpad/" in p


def _inside(path, root):
    """True if `path`, symlinks resolved, is `root` or below it."""
    p, r = Path(path).resolve(), Path(root).resolve()
    return p == r or r in p.parents


def verify_directory(directory, checksums, expected_sha256):
    """Exact verification of one directory. Raises on the first discrepancy
    class; never skips, never tolerates a count short of the list."""
    directory = Path(directory)
    if not directory.is_dir():
        raise DatasetGateError("dataset directory {0} does not exist".format(
            directory))
    listed = read_checksums(checksums)
    present = {p.name for p in directory.iterdir() if p.is_file()}
    missing = sorted(set(listed) - present)
    extra = sorted(present - set(listed))
    if missing or extra:
        raise DatasetGateError("file set differs from {0}: missing {1}, extra {2}"
                               .format(checksums, missing[:5], extra[:5]))
    entries, bad = {}, []
    for name in sorted(listed):
        path = directory / name
        digest = _sha256(path)
        if digest != listed[name]:
            bad.append(name)
        entries[name] = (path.stat().st_size, digest)
    if bad:
        raise DatasetGateError("{0} file(s) differ from their recorded SHA-256: {1}"
                               .format(len(bad), bad[:5]))
    actual = dataset_hash(entries)
    if actual != expected_sha256:
        raise DatasetGateError("dataset hash {0} does not equal the registered {1}"
                               .format(actual, expected_sha256))
    return len(entries)


def verify_dataset(dataset_id, expected_sha256=None):
    """Verify a registered dataset and return the path to load it from."""
    datasets = registry()["datasets"]
    if dataset_id not in datasets:
        raise DatasetGateError("{0!r} is not in {1}".format(dataset_id, REGISTRY))
    entry = datasets[dataset_id]
    if entry.get("status") != "preserved":
        raise DatasetGateError("{0} has status {1!r}; there is no verifiable copy"
                               .format(dataset_id, entry.get("status")))
    if expected_sha256 is not None and expected_sha256 != entry["sha256"]:
        raise DatasetGateError("the requested hash {0} is not the registered {1}"
                               .format(expected_sha256, entry["sha256"]))
    path = REPO / entry["path"]
    if _under_temp(path):
        raise DatasetGateError("{0} is under a temporary directory; a governed "
                               "dataset must be durable".format(path))
    if not _inside(path, RESEARCH_ROOT):
        raise DatasetGateError("{0} is outside {1}; a governed dataset lives "
                               "under the research data root".format(
                                   path, RESEARCH_ROOT))
    count = verify_directory(path, REPO / entry["checksums"], entry["sha256"])
    if count != entry["file_count"]:
        raise DatasetGateError("{0} files, registry says {1}".format(
            count, entry["file_count"]))
    return path


# ------------------------------------------------------------ runner helpers
# What governed runners call instead of finding data themselves. Added
# 2026-09-24: docs/2026-09-24-governed-research-dataset-migration.md

DECADE = "decade-2016-2026-split-adjusted-230"
DECADE_SHA256 = "935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7"
THIRTY_YEAR = "thirty-year-1996-2026-229"

#: The runners' own folder labels, mapped to registered datasets and the hash
#: each is pinned to. "long" names the lost thirty-year dataset, so it is always
#: refused - never resolved to whatever a temporary directory happens to hold.
PRICE_FOLDERS = {"deep": (DECADE, DECADE_SHA256), "long": (THIRTY_YEAR, None)}


def price_dir(folder):
    """The verified directory behind a runner's price-folder label. Fail-closed.

    Verification runs on every call, before the caller reads a bar: the exact
    file set, every SHA-256, the dataset hash (pinned here, so an edited
    registry is caught too), a durable path under the research data root.
    There is no fallback to any other copy.
    """
    if folder not in PRICE_FOLDERS:
        raise DatasetGateError("unknown price folder {0!r}; known: {1}".format(
            folder, sorted(PRICE_FOLDERS)))
    dataset_id, pinned = PRICE_FOLDERS[folder]
    return verify_dataset(dataset_id, pinned)


def decade_dir():
    """The verified decade dataset directory - `price_dir("deep")`."""
    return price_dir("deep")


def dataset_file(directory, name):
    """One file of a verified directory; raises if it is absent or would
    resolve outside that directory. Never returns a path to skip."""
    directory = Path(directory)
    path = directory / name
    if path.resolve().parent != directory.resolve():
        raise DatasetGateError("{0} resolves outside {1}".format(name, directory))
    if not path.is_file():
        raise DatasetGateError("{0} is not in the verified dataset at {1}".format(
            name, directory))
    return path


#: Stores that exist ONLY in a Claude session scratchpad and have no verified
#: copy. Listed so that no one can use `unpreserved_intraday_store` to reach
#: the decade price data ("deep") - that must come through `price_dir`.
UNPRESERVED_INTRADAY_STORES = (
    "raw/intraday-exits",      # H-0011 rule-exit sessions; H-0013 features
    "raw/intraday-spy",        # SPY 5-minute bars; H-0013, H-0014
    "raw/h0017-micro",         # H-0017 trade/quote payloads
    "snapshots",               # H-0014 intraday snapshots
    "intraday_cache",          # H-0008 five-minute bars - no longer present
)


def unpreserved_intraday_store(relpath):
    """Locate an UNVERIFIED intraday store in a Claude session scratchpad.

    NOT A GOVERNED DATASET. Nothing here is hashed or checked: these payloads
    were never preserved (docs/datasets/README.md, "Not covered here"), and
    results that depend on them are reproducible only while the scratchpad
    survives. It exists so that the one remaining kind of scratchpad access is
    explicit, named and auditable, and is keyed on the intraday store itself -
    not on the decade files - so it cannot become a route to decade data.
    Refuses unless exactly one scratchpad holds the store.
    """
    if relpath not in UNPRESERVED_INTRADAY_STORES:
        raise DatasetGateError("{0!r} is not a listed unpreserved intraday store; "
                               "decade price data comes only from price_dir()"
                               .format(relpath))
    pattern = os.path.join(os.environ.get("TEMP", "/tmp"), "claude",
                           "C--market-bot", "*", "scratchpad")
    hits = [Path(c) for c in sorted(glob.glob(pattern))
            if (Path(c) / relpath).exists()]
    if len(hits) != 1:
        raise DatasetGateError("{0} scratchpads hold {1!r}; exactly one is "
                               "required: {2}".format(len(hits), relpath, hits))
    return hits[0] / relpath


REQUIRED = ("dataset ID and SHA-256 in parameters['dataset']",
            "population in parameters['population']",
            "benchmark in parameters['benchmark']",
            "information_boundary", "execution_assumptions")


def check_registration(hypothesis):
    """Problems that must be fixed before a hypothesis may be registered.

    Accepts a `modelgov.prereg.Hypothesis` or a registration payload dict.
    """
    get = (hypothesis.get if isinstance(hypothesis, dict)
           else lambda k, d=None: getattr(hypothesis, k, d))
    params = get("parameters") or {}
    problems = []
    ds = params.get("dataset") if isinstance(params, dict) else None
    datasets = registry()["datasets"]
    if not isinstance(ds, dict) or not ds.get("id") or not ds.get("sha256"):
        problems.append("parameters['dataset'] must be {'id': ..., 'sha256': ...}")
    elif ds["id"] not in datasets:
        problems.append("dataset {0!r} is not registered in docs/datasets"
                        .format(ds["id"]))
    elif datasets[ds["id"]].get("status") != "preserved":
        problems.append("dataset {0!r} has no verifiable copy (status {1!r})"
                        .format(ds["id"], datasets[ds["id"]].get("status")))
    elif ds["sha256"] != datasets[ds["id"]]["sha256"]:
        problems.append("dataset SHA-256 does not match the registry")
    for key in ("population", "benchmark"):
        if not isinstance(params, dict) or not str(params.get(key, "")).strip():
            problems.append("parameters[{0!r}] must be stated".format(key))
    for key in ("information_boundary", "execution_assumptions"):
        if not str(get(key) or "").strip():
            problems.append("{0} must be stated".format(key))
    return problems


def audit():
    reg = registry()
    effective = reg["effective_date"]
    failed = 0
    for dataset_id, entry in sorted(reg["datasets"].items()):
        if entry.get("status") != "preserved":
            print("{0}: {1} - no verifiable copy; dependent results are "
                  "non-reproducible from preserved raw data".format(
                      dataset_id, entry.get("status")))
            continue
        try:
            path = verify_dataset(dataset_id)
            print("{0}: VERIFIED {1} files at {2} (sha256 {3}...)".format(
                dataset_id, entry["file_count"], path.relative_to(REPO),
                entry["sha256"][:16]))
        except DatasetGateError as error:
            failed += 1
            print("{0}: FAILED - {1}".format(dataset_id, error))
    grandfathered, gated = 0, 0
    for line in PREREG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)["payload"]
        if payload["registered_at"][:10] < effective:
            grandfathered += 1
            continue
        gated += 1
        problems = check_registration(payload)
        if problems:
            failed += 1
            print("{0}: registered {1} WITHOUT dataset identity - {2}".format(
                payload["hypothesis_id"], payload["registered_at"][:10],
                "; ".join(problems)))
    print("registrations: {0} before {1} (grandfathered), {2} on or after it"
          .format(grandfathered, effective, gated))
    print("RESULT: {0}".format("PASS" if not failed else
                               "FAIL - {0} problem(s)".format(failed)))
    return 0 if not failed else 1


def main(argv):
    if len(argv) >= 3 and argv[1] == "--verify":
        try:
            path = verify_dataset(argv[2])
        except DatasetGateError as error:
            print("REFUSED:", error)
            return 1
        print("VERIFIED", argv[2], "at", path)
        return 0
    return audit()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
