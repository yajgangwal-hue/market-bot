"""Validate the knowledge base in knowledge/. Read-only: it writes nothing.

Every check here is one the knowledge base claims to satisfy. A check that
fails is a defect in the vault, not something to be edited away:

  structure   every note has frontmatter with a known authority, a title, a
              `generated` flag and at least one source; every source exists
              and is tracked by git
  banners     every VALIDATED EVIDENCE / MEASUREMENT / INCONCLUSIVE / REJECTED /
              OPEN QUESTION / HISTORICAL note says NOT A PRODUCTION RULE, and
              NORMATIVE, FROZEN, REMEDIATION and NAVIGATION notes carry their
              own banner
  links       every [[wikilink]] resolves to exactly one note; every relative
              link resolves to a file git tracks (or to a note); every
              `file::symbol` code citation names a symbol still in that file
  quotations  every “verbatim quotation” of 12+ characters is found in a file
              linked in the same block, or in the note's `sources`
  identifiers every H-/EXP-/P5-/REM- identifier mentioned exists; every ledger
              row has exactly one note; no identifier is duplicated; each
              note's authority matches its ledger's vocabulary; SPEC-0001
              clause numbers are in range
  generation  every generated note equals what the builder produces now, and
              no generated note is orphaned
  guards      Production Truth's Active section links no REJECTED,
              INCONCLUSIVE, MEASUREMENT, OPEN QUESTION or HISTORICAL note; the
              Home coverage counts equal the ledgers; hand-written notes carry
              a Snapshot line
  production  src/ has no uncommitted change (reported, and failed)

Exit status 0 only when every check passes.
"""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

import build_knowledge_base as B  # noqa: E402

KB = B.KB
WIKI = re.compile(r"\[\[([^\]|#]+)(#[^\]|]*)?(\|[^\]]*)?\]\]")
MDLINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
QUOTE = re.compile(r"“([^”]{12,}?)”", re.S)
CODECITE = re.compile(r"^`([^`]+?)::(.+)`$")
SPEC_CLAUSE = re.compile(r"(?<![A-Za-z0-9-])C-(\d+)\b")

errors = defaultdict(list)


def err(check, msg):
    errors[check].append(msg)


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    return text[4:end], text[end + 5:]


def parse_frontmatter(block):
    """The small YAML subset the vault uses: scalars and one level of lists."""
    out, key = {}, None
    for line in block.splitlines():
        if line.startswith("  - "):
            out.setdefault(key, []).append(json.loads(line[4:]))
        elif ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val == "":
                out[key] = []
            elif val in ("true", "false"):
                out[key] = val == "true"
            else:
                out[key] = json.loads(val)
    return out


def strip_code(body):
    return re.sub(r"```.*?```", "", body, flags=re.S)


def blocks(body):
    """Paragraphs and list items; every table row is its own block."""
    for para in re.split(r"\n\s*\n", strip_code(body)):
        lines = para.splitlines()
        if lines and all(l.lstrip().startswith("|") for l in lines):
            for l in lines:
                yield l
        else:
            yield para


def pending_files():
    """Untracked files git would add - new work not yet committed. An IGNORED
    file is excluded: it will never be committed, so a link to it is broken
    for everyone but this machine."""
    out = subprocess.run(["git", "ls-files", "--others", "--exclude-standard",
                          "-z"], cwd=REPO, capture_output=True,
                         check=True).stdout
    return {p for p in out.decode("utf-8").split("\0") if p}


def main():
    tracked = B.tracked_files()
    pending = pending_files()
    pending_cited = set()
    notes = sorted(KB.rglob("*.md"))
    stems = Counter(p.stem for p in notes)
    for s, n in stems.items():
        if n > 1:
            err("links", "duplicate note name {0!r} ({1} files) - wikilinks "
                         "would be ambiguous".format(s, n))
    meta, bodies = {}, {}

    # ------------------------------------------------------------ structure
    for p in notes:
        text = p.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        rel = p.relative_to(REPO).as_posix()
        if fm is None:
            err("structure", rel + ": no frontmatter")
            continue
        m = parse_frontmatter(fm)
        meta[p], bodies[p] = m, body
        a = m.get("authority")
        if a not in B.AUTHORITIES:
            err("structure", "{0}: authority {1!r} is not a known level"
                .format(rel, a))
        for k in ("title", "generated", "sources"):
            if k not in m:
                err("structure", "{0}: missing {1}".format(rel, k))
        if not m.get("sources"):
            err("structure", rel + ": no sources")
        for s in m.get("sources", []):
            if not (REPO / s).exists():
                err("structure", "{0}: source {1} does not exist".format(rel, s))
            elif s in pending:
                pending_cited.add(s)
            elif s not in tracked:
                err("structure", "{0}: source {1} is ignored by git and "
                    "would be broken for anyone else".format(rel, s))
        if m.get("generated") is False and "*Snapshot:" not in body:
            err("guards", rel + ": hand-written note without a Snapshot line")

    # -------------------------------------------------------------- banners
    for p, m in meta.items():
        a, body, rel = m.get("authority"), bodies[p], p.relative_to(REPO)
        need = (B.NOT_A_RULE_MARK if a in B.NOT_A_RULE else
                "the source governs" if a in ("NORMATIVE", "FROZEN") else
                "REMEDIATION RECORD" if a == "REMEDIATION" else
                "NAVIGATION — non-authoritative")
        if need not in body:
            err("banners", "{0}: authority {1} but no {2!r} banner".format(
                rel, a, need))

    # ---------------------------------------------------------------- links
    stem_to_path = {p.stem: p for p in notes}
    headings = {p.stem: {re.sub(r"\s+", " ", h.strip().lower())
                         for h in re.findall(r"^#+\s+(.+)$", bodies.get(p, ""),
                                             re.M)}
                for p in notes}
    link_count = md_count = code_count = 0
    for p, body in bodies.items():
        rel = p.relative_to(REPO)
        clean = strip_code(body)
        for m in WIKI.finditer(clean):
            link_count += 1
            target = m.group(1).strip()
            if target not in stem_to_path:
                err("links", "{0}: [[{1}]] resolves to no note".format(
                    rel, target))
            elif m.group(2):
                h = re.sub(r"\s+", " ", m.group(2)[1:].strip().lower())
                if h not in headings[target]:
                    err("links", "{0}: heading {1!r} not in {2}".format(
                        rel, m.group(2), target))
        for m in MDLINK.finditer(clean):
            label, href = m.group(1), m.group(2)
            if href.startswith(("http://", "https://", "#")):
                continue
            md_count += 1
            target = (p.parent / href.split("#")[0]).resolve()
            try:
                trel = target.relative_to(REPO).as_posix()
            except ValueError:
                err("links", "{0}: link {1} leaves the repository".format(
                    rel, href))
                continue
            if not target.exists():
                err("links", "{0}: link {1} -> {2} does not exist".format(
                    rel, href, trel))
                continue
            if trel in pending:
                pending_cited.add(trel)
            elif not trel.startswith("knowledge/") and trel not in tracked:
                err("links", "{0}: link to {1}, which git ignores - broken for "
                    "anyone else".format(rel, trel))
            c = CODECITE.match(label)
            if c:
                code_count += 1
                if c.group(2) not in target.read_text(encoding="utf-8"):
                    err("links", "{0}: code citation {1!r} not found in {2}"
                        .format(rel, c.group(2), trel))

    # ----------------------------------------------------------- quotations
    quote_count = 0
    for p, body in bodies.items():
        rel = p.relative_to(REPO)
        sources = list(meta[p].get("sources", []))
        for blk in blocks(body):
            local = []
            for m in MDLINK.finditer(blk):
                href = m.group(2)
                if href.startswith(("http://", "https://", "#")):
                    continue
                t = (p.parent / href.split("#")[0]).resolve()
                if t.is_file():
                    try:
                        local.append(t.relative_to(REPO).as_posix())
                    except ValueError:
                        pass
            for m in QUOTE.finditer(blk):
                q = m.group(1).replace("\\|", "|")
                q = re.sub(r"\s+", " ", q).strip()
                if q.endswith("…"):
                    q = q[:-1]
                if len(q) < 12:
                    continue
                quote_count += 1
                cands = [c for c in local + sources
                         if (REPO / c).is_file()
                         and not c.startswith("knowledge/")]
                if not any(B.anchor_ok(c, q) for c in cands):
                    err("quotations", "{0}: “{1}” not found in {2}".format(
                        rel, q[:90], cands or "any cited file"))

    # ---------------------------------------------------------- identifiers
    L = B.Ledgers()
    for name, path in (("experiments", B.EXPERIMENTS), ("phase5", B.PHASE5)):
        ids = [r["id"] for _, r in B.load_jsonl(path)]
        for i, n in Counter(ids).items():
            if n > 1:
                err("identifiers", "{0}: {1} appears {2} times".format(
                    path, i, n))
    for path, key in ((B.PREREG, "hypothesis_id"), (B.REMEDIATIONS, "id")):
        ids = [r["payload"][key] for _, r in B.load_jsonl(path)]
        for i, n in Counter(ids).items():
            if n > 1:
                err("identifiers", "{0}: {1} appears {2} times".format(
                    path, i, n))
    expected = (set(L.exp) | set(L.p5) | set(L.h) | set(L.rem) | {"H-0022"})
    noted = Counter(m.get("id") for m in meta.values() if m.get("id"))
    for i, n in noted.items():
        if n > 1:
            err("identifiers", "{0} has {1} notes".format(i, n))
        if i not in expected:
            err("identifiers", "note for {0}, which no ledger holds".format(i))
    for i in sorted(expected - set(noted)):
        err("identifiers", "{0} has no note".format(i))
    for p, m in meta.items():
        i = m.get("id")
        if not i:
            continue
        if p.stem != i:
            err("identifiers", "{0}: file name does not match id {1}".format(
                p.relative_to(REPO), i))
        want = (B.EXP_AUTHORITY[L.exp[i][1]["decision"]] if i in L.exp else
                B.P5_AUTHORITY[L.p5[i][1]["verdict"]] if i in L.p5 else
                "REMEDIATION" if i in L.rem else B.CURATED[i]["authority"])
        if m.get("authority") != want:
            err("identifiers", "{0}: authority {1} but its ledger maps to {2}"
                .format(i, m.get("authority"), want))
    _, _, clauses = B.render_spec_clauses()
    mentioned = 0
    for p, body in bodies.items():
        clean = strip_code(body)
        for i in set(B.ID_RE.findall(clean)):
            mentioned += 1
            if i in B.KNOWN_ABSENT:
                if "[[{0}]]".format(i) in clean:
                    err("identifiers", "{0}: wikilinks {1}, which does not "
                        "exist".format(p.relative_to(REPO), i))
            elif not L.exists(i):
                err("identifiers", "{0}: mentions {1}, which no ledger holds"
                    .format(p.relative_to(REPO), i))
        for c in SPEC_CLAUSE.findall(clean):
            if int(c) not in clauses:
                err("identifiers", "{0}: C-{1} is not a SPEC-0001 clause"
                    .format(p.relative_to(REPO), c))

    # ----------------------------------------------------------- generation
    built = B.build()
    for path, text in built.items():
        if not path.exists():
            err("generation", "missing generated note {0}".format(
                path.relative_to(REPO)))
        elif path.read_text(encoding="utf-8") != text:
            err("generation", "stale generated note {0} - rerun "
                "scripts/build_knowledge_base.py".format(path.relative_to(REPO)))
    for p, m in meta.items():
        if m.get("generated") and p not in built:
            err("generation", "orphaned generated note {0}".format(
                p.relative_to(REPO)))

    # --------------------------------------------------------------- guards
    pt = stem_to_path.get("Production Truth")
    if pt is None:
        err("guards", "no Production Truth note")
    else:
        body = bodies[pt]
        active = body.split("## Active", 1)[-1].split("\n## ", 1)[0]
        forbidden = {"REJECTED", "INCONCLUSIVE", "MEASUREMENT",
                     "OPEN QUESTION", "HISTORICAL"}
        for m in WIKI.finditer(active):
            t = stem_to_path.get(m.group(1).strip())
            if t is not None and meta[t].get("authority") in forbidden:
                err("guards", "Production Truth / Active links [[{0}]] "
                    "({1})".format(t.stem, meta[t]["authority"]))
    home = stem_to_path.get("Home")
    if home is not None:
        want = {"registered hypotheses": len(L.h),
                "phase-5 executions": len(L.p5),
                "experiments": len(L.exp), "remediations": len(L.rem),
                "SPEC-0001 clauses": len(clauses)}
        for label, n in want.items():
            if "| {0} | {1} |".format(label, n) not in bodies[home]:
                err("guards", "Home coverage row {0!r} does not equal the "
                    "ledger count {1}".format(label, n))

    # ----------------------------------------------------------- production
    out = subprocess.run(["git", "status", "--porcelain", "--", "src/"],
                         cwd=REPO, capture_output=True, text=True).stdout
    if out.strip():
        err("production", "src/ has uncommitted changes:\n" + out)

    # -------------------------------------------------------------- report
    counts = Counter(m.get("authority") for m in meta.values())
    print("notes            {0} ({1} generated, {2} hand-written)".format(
        len(meta), sum(1 for m in meta.values() if m.get("generated")),
        sum(1 for m in meta.values() if m.get("generated") is False)))
    print("authority        " + ", ".join("{0} {1}".format(k, v) for k, v in
                                           sorted(counts.items())))
    print("wikilinks        {0}".format(link_count))
    print("file links       {0} ({1} code citations)".format(md_count,
                                                             code_count))
    print("quotations       {0} checked".format(quote_count))
    print("identifiers      {0} mentions checked; {1} ledger items".format(
        mentioned, len(expected)))
    print("spec clauses     {0}".format(len(clauses)))
    outside = sorted(f for f in pending_cited if not f.startswith("knowledge/"))
    if outside:
        print("not yet committed, cited by the vault - commit them with it:")
        for f in outside:
            print("    " + f)
    checks = ("structure", "banners", "links", "quotations", "identifiers",
              "generation", "guards", "production")
    failed = 0
    for c in checks:
        n = len(errors.get(c, []))
        failed += n
        print("{0:12s}     {1}".format(c, "PASS" if not n else
                                        "FAIL ({0})".format(n)))
        for e in errors.get(c, [])[:40]:
            print("    - " + e)
    print("RESULT           {0}".format("PASS" if not failed else
                                        "FAIL - {0} problem(s)".format(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
