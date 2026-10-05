"""Build the GENERATED half of the knowledge base from the governed ledgers.

The knowledge base in knowledge/ is DOCUMENTATION. It is not a source of
trading decisions, nothing in the money path reads it, and no note in it can
authorise a change. The governed artefacts it points at remain authoritative.

WHAT THIS SCRIPT OWNS. Every note it writes carries `generated: true` in its
frontmatter and is rewritten in full on each run, so the ledgers stay the only
source of record for the facts in it:

  03-research/hypotheses/H-*.md      docs/preregistrations.jsonl + CURATED
  03-research/phase5/P5-*.md         docs/phase5-research.jsonl
  03-research/experiments/EXP-*.md   docs/experiments.jsonl
  04-remediation/records/REM-*.md    docs/remediations.jsonl
  03-research/Research Index.md
  03-research/Do Not Re-Research.md  AREAS + the ledgers
  04-remediation/Remediation Index.md
  01-frozen/Frozen Parameters.md     the frozen config objects themselves
  01-frozen/SPEC-0001 Clauses.md     docs/SPEC-0001-decision-boundary.md
  07-sources/Reports Catalogue.md    every Markdown document outside knowledge/

A note WITHOUT `generated: true` is hand-written. This script never touches
one, and refuses to run if it would.

WHAT IS CURATED, AND HOW IT IS KEPT HONEST. A hypothesis's outcome lives in its
report, not in a ledger field, so CURATED records it - but only as a VERBATIM
quotation together with the file it is quoted from. Every quotation is checked
against that file before anything is written, and one that does not match
stops the build. Nothing in CURATED paraphrases a result; the authority level
it assigns is a documented classification, and the rule applied is printed on
every note beside the quotation it rests on.

Usage:
  python scripts/build_knowledge_base.py            write the generated notes
  python scripts/build_knowledge_base.py --check    verify, write nothing
"""

import dataclasses
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KB = REPO / "knowledge"
sys.path.insert(0, str(REPO / "src"))

EXPERIMENTS = "docs/experiments.jsonl"
PHASE5 = "docs/phase5-research.jsonl"
PREREG = "docs/preregistrations.jsonl"
REMEDIATIONS = "docs/remediations.jsonl"
SPEC = "docs/SPEC-0001-decision-boundary.md"

# ---------------------------------------------------------------------------
# Authority levels. The validator imports these, so there is one definition.
# ---------------------------------------------------------------------------

AUTHORITIES = (
    "NORMATIVE", "FROZEN", "VALIDATED EVIDENCE", "MEASUREMENT", "INCONCLUSIVE",
    "REJECTED", "REMEDIATION", "OPEN QUESTION", "HISTORICAL", "NAVIGATION",
)
#: Every note at one of these levels must carry the NOT-A-PRODUCTION-RULE banner.
NOT_A_RULE = ("VALIDATED EVIDENCE", "MEASUREMENT", "INCONCLUSIVE", "REJECTED",
              "OPEN QUESTION", "HISTORICAL")
NOT_A_RULE_MARK = "NOT A PRODUCTION RULE"

#: experiments.jsonl `decision` -> authority. purge.CONFIG_CHANGING is
#: {accepted, reverted}: only those two ever moved the shipped configuration.
EXP_AUTHORITY = {
    "accepted": "VALIDATED EVIDENCE",
    "reverted": "REJECTED",
    "rejected": "REJECTED",
    "measured": "MEASUREMENT",
    "inconclusive": "INCONCLUSIVE",
}
#: phase5-research.jsonl `verdict` -> authority, per phase5/ledger.py VERDICTS.
P5_AUTHORITY = {
    "rejected": "REJECTED",
    "inconclusive": "INCONCLUSIVE",
    "research_evidence": "INCONCLUSIVE",   # "promising, on contaminated data, proves nothing"
    "promotion_candidate": "VALIDATED EVIDENCE",
}

ID_RE = re.compile(r"\b(H-\d{4}|EXP-\d{4}|P5-\d{4}|REM-\d{4})\b")

#: The lost thirty-year dataset (docs/datasets/thirty-year-1996-2026.md). The
#: selection rules below are the ones that datasheet states.
THIRTY_YEAR_SHEET = "docs/datasets/thirty-year-1996-2026.md"


def uses_thirty_year(kind, row):
    if kind == "exp":
        return "thirty_year" in row["data_periods"]
    if kind == "p5":
        keys = list((row.get("metrics") or {}).keys()) + list(
            (row.get("difference_from_baseline") or {}).keys())
        return ("thirty" in str(row.get("dataset", "")).lower()
                or any(k.startswith("thirty_year") for k in keys))
    if kind == "h":
        return any("thirty" in d.lower() and "not used" not in d.lower()
                   for d in row["datasets"])
    raise ValueError(kind)


def thirty_year_caveat(note_path):
    return ("> [!caution] Thirty-year data — non-reproducible\n> This item "
            "used the thirty-year dataset, whose raw data is **lost**. Its "
            "thirty-year figures stand as recorded but cannot be re-derived "
            "from preserved raw data; any decade figures can — {0}.\n".format(
                link_to(note_path, THIRTY_YEAR_SHEET, "thirty-year datasheet")))
#: Identifiers that are cited in the knowledge base BECAUSE they do not exist.
KNOWN_ABSENT = {"EXP-0053": "numbering gap in experiments.jsonl; referenced "
                            "nowhere in tracked files or git history"}

# ---------------------------------------------------------------------------
# CURATED: hypothesis outcomes, each a verbatim quotation from a named file.
# ---------------------------------------------------------------------------

H_REPORTS = {
    "H-0007": ["docs/2026-09-17-h0007-report.md"],
    "H-0008": ["docs/2026-09-17-h0008-report.md"],
    "H-0009": ["docs/2026-09-19-h0009-report.md"],
    "H-0010": ["docs/2026-09-19-h0010-report.md"],
    "H-0011": ["docs/2026-09-20-h0011-report.md",
               "docs/2026-09-20-h0011-validation-gate.md"],
    "H-0012": ["docs/2026-09-20-h0012-report.md"],
    "H-0013": ["docs/2026-09-20-h0013-report.md"],
    "H-0014": ["docs/2026-09-20-h0014-report.md"],
    "H-0015": ["docs/2026-09-21-h0015-stop-report.md"],
    "H-0016": ["docs/2026-09-21-h0016-report.md"],
    "H-0017": ["docs/2026-09-21-h0017-report.md"],
    "H-0018": ["docs/2026-09-21-h0018-report.md"],
    "H-0019": ["docs/2026-09-21-h0019-opportunity-generation-audit.md"],
    "H-0020": ["docs/2026-09-21-h0020-p3-validation.md"],
    "H-0021": ["docs/2026-09-21-h0021-giveback-anatomy.md",
               "docs/2026-09-21-h0021-candidate-design.md"],
    "H-0022": ["docs/2026-09-22-h0019-recognized-gains-news-audit.md"],
    "H-0023": ["docs/2026-09-22-h0023-survivorship-ceiling-audit.md"],
    "H-0024": ["docs/2026-09-22-h0024-capability-gap-report.md"],
    "H-0025": ["docs/2026-09-23-h0025-gain-to-loss-forensics.md"],
    "H-0026": ["docs/2026-09-28-h0026-report.md"],
    "H-0027": ["docs/2026-10-03-shorting-and-all-in-report.md"],
    "H-0028": ["docs/2026-10-03-shorting-and-all-in-report.md"],
    "H-0029": ["docs/2026-10-03-shorting-and-all-in-report.md"],
    "H-0030": ["docs/2026-10-03-shorting-and-all-in-report.md"],
    "H-0031": ["docs/2026-10-03-shorting-and-all-in-report.md"],
    "H-0032": ["docs/2026-10-03-day-trading-what-works.md"],
    "H-0033": ["docs/2026-10-03-day-trading-what-works.md"],
    "H-0034": ["docs/2026-10-04-what-else-day-traders-do.md"],
    "H-0035": ["docs/2026-10-04-what-else-day-traders-do.md"],
    "H-0036": ["docs/2026-10-04-day-trading-everything-else.md"],
    "H-0037": ["docs/2026-10-04-where-to-take-profit.md"],
    "H-0038": ["docs/2026-10-04-where-to-take-profit.md"],
    "H-0039": ["docs/2026-10-04-futures-trend-h0039.md"],
}

# title, authority, the registered outcome letter (or None), the rule applied,
# and the verbatim quotations the outcome rests on: (file, quotation).
CURATED = {
    "H-0001": dict(
        title="Trailing stop, armed after a threshold gain",
        authority="REJECTED", letter=None,
        rule="phase-5 verdict `rejected` on its execution P5-0007",
        quotes=[(PHASE5, "REJECTED on the registered clauses.")]),
    "H-0002": dict(
        title="Fixed take profit",
        authority="INCONCLUSIVE", letter=None,
        rule="phase-5 verdict `research_evidence` on P5-0008 and on its "
             "correction P5-0014; that verdict means \"promising, on "
             "contaminated data, proves nothing\" (phase5/ledger.py)",
        quotes=[(PHASE5, "REGISTERED AS EXPECTED TO FAIL, and it did not."),
                (PHASE5, "P5-0008 stands unedited; this row supersedes its "
                         "metrics."),
                (PHASE5, "This contradicts the earlier finding that every "
                         "binding take-profit level cost return - that work "
                         "predated the haircut and the participation cap.")]),
    "H-0003": dict(
        title="Breakeven profit lock",
        authority="INCONCLUSIVE", letter=None,
        rule="phase-5 verdict `research_evidence` on P5-0009",
        quotes=[(PHASE5, "NOT a promotion candidate on this evidence; it "
                         "earns a new registration.")]),
    "H-0004": dict(
        title="Scaling out half at a target",
        authority="REJECTED", letter=None,
        rule="phase-5 verdict `rejected` on P5-0010",
        quotes=[(PHASE5, "Rejected on both settings")]),
    "H-0005": dict(
        title="Is the 1.0R lock a gradient or a spike?",
        authority="REJECTED", letter=None,
        rule="phase-5 verdict `rejected` on P5-0015, P5-0016, P5-0017 and "
             "the family row P5-0018",
        quotes=[(PHASE5, "is nevertheless NOT accepted, because the family "
                         "it belongs to is violently non-monotone")]),
    "H-0006": dict(
        title="Idle capital in the index",
        authority="REJECTED", letter=None,
        rule="phase-5 verdict `rejected` on all three executions, P5-0019, "
             "P5-0020 and P5-0021",
        quotes=[(PHASE5, "Failed clauses: volatility within 110% of "
                         "baseline, drawdown within 110% of baseline.")]),
    "H-0007": dict(
        title="Volatility-percentile entry abstention",
        authority="REJECTED", letter=None,
        rule="the report's own decision, corroborated by "
             "docs/phase5/h0007-adjudication.json verdict REJECTED",
        quotes=[("docs/2026-09-17-h0007-report.md", "Verdict: REJECTED.")]),
    "H-0008": dict(
        title="Is the 0.652% rule-exit haircut defensible?",
        authority="REJECTED", letter=None,
        rule="the report's own decision. What was rejected is the hypothesis "
             "that the haircut is too conservative; the haircut itself "
             "stands. Corroborated by h0008-adjudication.json",
        quotes=[("docs/2026-09-17-h0008-report.md",
                 "Decision: REJECTED. The 0.652% haircut stands unchanged")]),
    "H-0009": dict(
        title="Slot competition at RSI 36/37/38",
        authority="REJECTED", letter=None,
        rule="the report's own decision, corroborated by "
             "h0009-adjudication.json",
        quotes=[("docs/2026-09-19-h0009-report.md",
                 "Passing A, B, C and D: none. VERDICT: REJECTED.")]),
    "H-0010": dict(
        title="Stop width and a 2.5R take profit",
        authority="REJECTED", letter=None,
        rule="the report's own decision, corroborated by "
             "h0010-adjudication.json",
        quotes=[("docs/2026-09-19-h0010-report.md",
                 "Decision: REJECTED on clauses B, C and E.")]),
    "H-0011": dict(
        title="Resting-limit exits, the day-trading research's one reachable "
              "lead",
        authority="INCONCLUSIVE", letter=None,
        rule="the report's own decision, corroborated by "
             "h0011-adjudication.json; a separate non-promotional validation "
             "gate then classified it B",
        quotes=[("docs/2026-09-20-h0011-report.md", "Decision: INCONCLUSIVE."),
                ("docs/2026-09-20-h0011-validation-gate.md",
                 "Conclusion: B — H-0011 REPRODUCIBLE BUT FRAGILE")]),
    "H-0012": dict(
        title="The yardstick audit",
        authority="INCONCLUSIVE", letter="C",
        rule="the registration's own stability gate defines C as "
             "\"measurable but unstable\"",
        quotes=[("docs/2026-09-20-h0012-report.md",
                 "Verdict: C — REPRICING MEASURABLE BUT UNSTABLE"),
                (PREREG, "the verdict is C (measurable but unstable) EVEN IF "
                         "the level test passes")]),
    "H-0013": dict(
        title="Stable point-in-time execution model audit",
        authority="INCONCLUSIVE", letter="B",
        rule="registered B is a mixed result: one component stable, the "
             "other not; the report adopts no model",
        quotes=[("docs/2026-09-20-h0013-report.md",
                 "Verdict: B — PARTIALLY STABLE"),
                ("docs/2026-09-20-h0013-report.md",
                 "No model is adopted, nothing is promoted, production is "
                 "unchanged.")]),
    "H-0014": dict(
        title="Intraday decision capability audit",
        authority="INCONCLUSIVE", letter="B",
        rule="registered B: information exists, edge not demonstrated",
        quotes=[("docs/2026-09-20-h0014-report.md",
                 "CLASSIFICATION: B — INFORMATION EXISTS, EDGE NOT YET "
                 "DEMONSTRATED")]),
    "H-0015": dict(
        title="Capacity audit — STOPPED at the §14 governance gate",
        authority="INCONCLUSIVE", letter=None,
        rule="the experiment stopped before reaching any registered "
             "outcome; nothing was concluded",
        quotes=[("docs/2026-09-21-h0015-stop-report.md",
                 "H-0015 — STOPPED at the §14 governance gate")]),
    "H-0016": dict(
        title="Cash/notional capacity audit",
        authority="REJECTED", letter="C",
        rule="registered C: the hypothesised suppression of economically "
             "meaningful opportunity was not supported",
        quotes=[("docs/2026-09-21-h0016-report.md",
                 "CLASSIFICATION: C — CASH CONSTRAINT IS NOT ECONOMICALLY "
                 "IMPORTANT")]),
    "H-0017": dict(
        title="Targeted microstructure measurement, 221 reverted exits",
        authority="VALIDATED EVIDENCE", letter="A",
        rule="registered A for a measurement-only seal; validates the "
             "measured execution facts, licenses no economic experiment. The "
             "report's A label is worded differently from the registered A "
             "- see Conflicts and Ambiguities",
        quotes=[("docs/2026-09-21-h0017-report.md",
                 "Classification: A — EXECUTION QUESTION SUBSTANTIALLY "
                 "NARROWED")]),
    "H-0018": dict(
        title="Economic value of resolving queue uncertainty",
        authority="INCONCLUSIVE", letter="B",
        rule="registered B: measurement value exists, economic leverage not "
             "established",
        quotes=[("docs/2026-09-21-h0018-report.md",
                 "Classification: B — MEASUREMENT VALUE EXISTS, BUT ECONOMIC "
                 "LEVERAGE IS NOT ESTABLISHED")]),
    "H-0019": dict(
        title="Opportunity generation capability audit",
        authority="VALIDATED EVIDENCE", letter="A",
        rule="registered A validates the gap MEASUREMENT and nominates one "
             "class (P3) for separate validation; H-0020 then found no "
             "evidence for P3",
        quotes=[("docs/2026-09-21-h0019-opportunity-generation-audit.md",
                 "Classification: A — MATERIAL OPPORTUNITY-GENERATION GAP"),
                ("docs/2026-09-21-h0019-opportunity-generation-audit.md",
                 "P4 collapses.")]),
    "H-0020": dict(
        title="Validation of the P3 population",
        authority="REJECTED", letter="C",
        rule="registered C: no evidence",
        quotes=[("docs/2026-09-21-h0020-p3-validation.md",
                 "Classification: C — NO EVIDENCE")]),
    "H-0021": dict(
        title="Give-back anatomy against an executable peak",
        authority="VALIDATED EVIDENCE", letter="A",
        rule="registered A validates the give-back MEASUREMENT only; the "
             "follow-up design produced no candidate",
        quotes=[("docs/2026-09-21-h0021-giveback-anatomy.md",
                 "Classification: A — A MATERIAL, EXECUTABLE GIVE-BACK "
                 "POPULATION EXISTS"),
                ("docs/2026-09-21-h0021-candidate-design.md",
                 "Outcome: NO NEW CANDIDATE.")]),
    "H-0022": dict(
        title="Recognized gains and news information — capability audit",
        authority="INCONCLUSIVE", letter=None,
        rule="UNREGISTERED: no seal exists, and unregistered work is never "
             "classified above INCONCLUSIVE. The report's own C "
             "classification is quoted, not adopted",
        quotes=[("docs/2026-09-22-h0019-recognized-gains-news-audit.md",
                 "The next free identifier is H-0022"),
                ("docs/2026-09-22-h0019-recognized-gains-news-audit.md",
                 "No experiment registered."),
                ("docs/2026-09-22-h0019-recognized-gains-news-audit.md",
                 "Classification: C — CURRENT ACCOUNTING/NEWS CAPABILITY IS "
                 "NOT THE BOTTLENECK")]),
    "H-0023": dict(
        title="Survivorship-complete profitability ceiling audit",
        authority="INCONCLUSIVE", letter="D",
        rule="registered D: a data limitation prevented the measurement",
        quotes=[("docs/2026-09-22-h0023-survivorship-ceiling-audit.md",
                 "Classification: D — PIT UNIVERSE CANNOT BE RECONSTRUCTED "
                 "RELIABLY")]),
    "H-0024": dict(
        title="Intraday strategy capability gap audit",
        authority="INCONCLUSIVE", letter="B",
        rule="registered B: capability gap exists, economic value not "
             "established",
        quotes=[("docs/2026-09-22-h0024-capability-gap-report.md",
                 "Classification: B — CAPABILITY GAP EXISTS, ECONOMIC VALUE "
                 "NOT ESTABLISHED")]),
    "H-0025": dict(
        title="Gain-to-loss forensics under the canonical execution boundary",
        authority="INCONCLUSIVE", letter="B",
        rule="registered B: evidence is weak or inconclusive; no candidate",
        quotes=[("docs/2026-09-23-h0025-gain-to-loss-forensics.md",
                 "Evidence is weak / inconclusive."),
                ("docs/2026-09-23-h0025-gain-to-loss-forensics.md",
                 "None is justified. No proposal is made.")]),
    "H-0026": dict(
        title="Take profit learned walk-forward from the strategy's own "
              "post-entry process",
        authority="REJECTED", letter="B",
        rule="registered B: rejected on the sealed clauses",
        quotes=[("docs/2026-09-28-h0026-report.md",
                 "Classification: B — REJECTED on clauses A, E, D, F, G")]),
    "H-0027": dict(
        title="Failed-rally short sleeve at equal notional, beside the long book",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-03-shorting-and-all-in-report.md",
                 "Classification: REJECTED for all five hypotheses.")]),
    "H-0028": dict(
        title="Failed-rally short sleeve, new shorts only in a confirmed bear tape",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-03-shorting-and-all-in-report.md",
                 "Classification: REJECTED for all five hypotheses.")]),
    "H-0029": dict(
        title="Relative-weakness breakdown (momentum) short sleeve",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-03-shorting-and-all-in-report.md",
                 "Classification: REJECTED for all five hypotheses.")]),
    "H-0030": dict(
        title="Fixed +0.5% target / -0.2% stop against the frozen exits, long and short signals",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-03-shorting-and-all-in-report.md",
                 "Classification: REJECTED for all five hypotheses.")]),
    "H-0031": dict(
        title="One position at a time with 99% of the account",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-03-shorting-and-all-in-report.md",
                 "Classification: REJECTED for all five hypotheses.")]),
    "H-0032": dict(
        title="Market intraday momentum on SPY as a day trade",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-03-day-trading-what-works.md",
                 "Verdict: REJECTED")]),
    "H-0033": dict(
        title="Published 'Beat the Market' noise-area intraday momentum on SPY, after publication",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-03-day-trading-what-works.md",
                 "Verdict: REJECTED, both versions")]),
    "H-0034": dict(
        title="Published 5-minute opening range breakout on SPY, after publication",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-04-what-else-day-traders-do.md",
                 "All five criteria fail.")]),
    "H-0035": dict(
        title="Published VWAP trend rule on SPY 5-minute candles, after publication",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-04-what-else-day-traders-do.md",
                 "(R2 fails).")]),
    "H-0036": dict(
        title="The 7,846-rule technical-analysis universe as SPY day trades",
        authority="REJECTED", letter=None,
        rule="registered: REJECTED on the sealed criteria",
        quotes=[("docs/2026-10-04-day-trading-everything-else.md",
                 "The sealed criteria needed both corrected tests below")]),
    "H-0037": dict(
        title="Take profit at the bounce price vs 2.5 ATR - registered, did not complete",
        authority="INCONCLUSIVE", letter=None,
        rule="registered; the runner crashed in its verdict step before any result was produced; superseded by H-0038",
        quotes=[("docs/2026-10-04-where-to-take-profit.md",
                 "H-0037 never completed.")]),
    "H-0038": dict(
        title="Take profit at the bounce price vs the live 2.5-ATR take profit, replayed on 698 trades",
        authority="INCONCLUSIVE", letter=None,
        rule="registered: NO DIFFERENCE SHOWN on the sealed criteria",
        quotes=[("docs/2026-10-04-where-to-take-profit.md",
                 "Verdict: NO DIFFERENCE SHOWN.")]),
    "H-0039": dict(
        title="Diversified trend following on 19 futures markets (fund proxies), 2008-2026",
        authority="VALIDATED EVIDENCE", letter=None,
        rule=("registered: NOT REJECTED on the sealed criteria - historical in-sample data, "
              "which can reject but not accept; nominated for a forward paper test, nothing live"),
        quotes=[("docs/2026-10-04-futures-trend-h0039.md",
                 "Verdict: NOT REJECTED - nominated for a forward paper test.")]),
}

#: Findings whose exact wording must survive, as (label, file, quotation). The
#: label is a navigation heading; the quotation is the finding, verbatim.
_H25 = "docs/2026-09-23-h0025-gain-to-loss-forensics.md"
_H21 = "docs/2026-09-21-h0021-giveback-anatomy.md"
FINDINGS = {
    "H-0025": [
        ("Conclusion", _H25, "Evidence is weak / inconclusive."),
        ("Gain-to-loss transition — what H-0025 newly established", _H25,
         "YES — established, and genuinely new. 87 trades crossed +2% "
         "executable and realised a loss, −$57,208, 21.0% of crossings, 23.3% "
         "of the book's total losses, present in all three chronological "
         "thirds."),
        ("Why it was not isolated before", _H25,
         "H-0021's seal excluded all 239 stop exits"),
        ("What prevents it becoming an exit candidate", _H25,
         "NO — not supported. 81.2% of +2% crossers go on to a higher "
         "executable gain."),
        ("Normal winner development vs tail give-back", _H25,
         "The median trade gives back nothing. +0.07% is the haircut itself "
         "— the median crosser exits at its executable peak. The give-back is "
         "entirely a tail phenomenon: median +0.07%, p90 +8.39%."),
        ("The three populations, never merged", _H25,
         "A = profitable, kept ≥50% of the executable peak. B = profitable, "
         "kept <50%. C = realised a loss. The 50% cut is a reporting "
         "convention declared in the seal, not a tuned parameter"),
        ("Crossing-time features", _H25,
         "A volatility-triggered protective exit would be backwards."),
        ("Crossing-time features", _H25,
         "RSI — the strategy's own exit input — carries no information at "
         "the crossing moment."),
        ("Executable vs hindsight information", _H25,
         "No figure in §C, §D or §E uses a hindsight price."),
        ("Relationship to H-0021", _H25,
         "H-0021's execution_assumptions say next-open fills are \"exactly "
         "what the frozen entry mechanism already assumes,\" and they are "
         "not"),
        ("Relationship to H-0021", _H25,
         "My reconstruction reproduces H-0021's next-open figures exactly"),
        ("Relationship to H-0021", _H25,
         "The one thing the correction does change is the median: 82.7% → "
         "97.9%"),
        ("Relationship to H-0021", _H25,
         "Correcting to the canonical boundary moves the give-back from "
         "+1.433% to +1.389%"),
        ("Relationship to H-0021", _H25,
         "H-0021's conclusion survives its own broken premise."),
        ("Unsettled — a monitoring item, not a hypothesis", _H25,
         "Gain-to-loss share by chronological third at +2%: 14.3% / 23.2% / "
         "24.4%"),
        ("Future research", _H25, "None is justified. No proposal is made."),
    ],
    "H-0021": [
        ("Executable vs hindsight peaks", _H21,
         "Half the apparent leakage vanishes the moment you require an "
         "executable price."),
        ("Where the give-back is", _H21,
         "The RSI exit has negative give-back."),
        ("Where the give-back is", _H21,
         "The biggest winners give back essentially nothing."),
        ("Stop exits", _H21,
         "Stops are reported separately and excluded from the pool, per the "
         "seal"),
        ("What it does not license", _H21,
         "It is not a candidate, and it is not evidence of recoverability."),
        ("Execution boundary — later corrected by H-0025", PREREG,
         "H-0021 measured give-back but (a) against next-open rather than the "
         "canonical signal-close boundary"),
    ],
}

#: Relationships between items that a source states explicitly. Each is
#: (from, to, relation, file, verbatim quotation establishing it).
RELATIONS = [
    ("H-0003", "H-0005", "the lock's result earned a new registration, which "
     "H-0005 is", PHASE5, "it earns a new registration."),
    ("H-0005", "H-0003", "tests the H-0003 lock below its 1.0R trigger",
     PREREG, "The breakeven lock's +13.71 points at a 1.0R trigger"),
    ("H-0002", "EXP-0050", "states that it contradicts the earlier "
     "take-profit finding (see Conflicts and Ambiguities)", PHASE5,
     "This contradicts the earlier finding that every binding take-profit "
     "level cost return"),
    ("H-0020", "H-0019", "validates the P3 population that H-0019 nominated",
     PREREG, "The P3 population excluded by the 3.5% ATR ceiling"),
    ("H-0025", "H-0021", "revisits H-0021's execution boundary and its "
     "exclusion of stop exits", PREREG, "H-0021 measured give-back but"),
    ("H-0013", "SPEC-0001", "SPEC-0001 is derived in part from H-0013's "
     "sealed methodology", SPEC,
     "Derived from sealed experiment methodology (H-0013)"),
    ("H-0013", "REM-0009", "REM-0009 records that H-0013 is preserved",
     REMEDIATIONS, "H-0013 preserved"),
    ("H-0022", "H-0019", "shares H-0019's filename prefix; it is a different "
     "audit (see Conflicts and Ambiguities)",
     "docs/2026-09-22-h0019-recognized-gains-news-audit.md",
     "This work was commissioned as \"H-0019\"."),
    ("REM-0009", "SPEC-0001", "implements clauses C-1 and C-19",
     REMEDIATIONS, "SPEC-0001 v1.0.0, clauses C-1, C-19"),
]

#: Explicit specification links, each stated by a source.
SPEC_LINKS = {
    "H-0013": ("C-1 context: SPEC-0001's authority row", SPEC,
               "Derived from sealed experiment methodology (H-0013)"),
    "H-0025": ("C-1: the canonical execution boundary it measures under",
               PREREG, "Under the CANONICAL SPEC-0001 execution boundary"),
    "REM-0009": ("C-1, C-19", REMEDIATIONS,
                 "SPEC-0001 v1.0.0, clauses C-1, C-19"),
}

# ---------------------------------------------------------------------------
# AREAS for the Do-Not-Re-Research map. The grouping is a navigation choice;
# every row it produces is the ledger's own text.
# ---------------------------------------------------------------------------

AREAS = [
    ("Trailing stops", ["EXP-0036", "H-0001", "P5-0007", "EXP-0035"], None,
     []),
    ("Fixed profit targets (take profit)",
     ["EXP-0049", "EXP-0050", "EXP-0051", "EXP-0052", "H-0002", "P5-0008",
      "P5-0014", "H-0010", "H-0026", "H-0030", "H-0037", "H-0038"],
     "The ledgers disagree here. H-0002 records research_evidence at 2.0R "
     "while EXP-0050 records that return falls as the target tightens. Both "
     "are preserved - see [[Conflicts and Ambiguities]].", []),
    ("Breakeven / profit lock",
     ["H-0003", "P5-0009", "H-0005", "P5-0015", "P5-0016", "P5-0017",
      "P5-0018"], None, []),
    ("Partial profit-taking (scaling out)", ["EXP-0036", "H-0004", "P5-0010"],
     None, []),
    ("RSI thresholds (exit and entry)",
     ["EXP-0023", "EXP-0006", "H-0009", "P5-0031", "P5-0032", "P5-0033",
      "P5-0034"], None, []),
    ("Time exit / holding period",
     ["EXP-0019", "EXP-0024", "H-0001", "H-0021"], None, []),
    ("Volatility-triggered exits", ["H-0025", "H-0007", "EXP-0009"],
     "NOT TESTED AS A RULE. No row in experiments.jsonl, "
     "phase5-research.jsonl or preregistrations.jsonl registers or runs a "
     "volatility-triggered exit. The rows below are related evidence only: "
     "H-0025 measured crossing-time ATR/price as a feature (no rule), H-0007 "
     "tested volatility-based ENTRY abstention, EXP-0009 tested volatility "
     "SIZING. None of them is evidence about a volatility exit.", []),
    ("Regime-conditioned exits, entries and sizing",
     ["EXP-0036", "EXP-0051", "EXP-0052", "EXP-0009", "EXP-0042", "EXP-0043",
      "EXP-0044", "EXP-0045", "EXP-0047", "H-0007", "P5-0022"], None,
     ["docs/2026-09-17-regime-forensics.md"]),
    ("Stop width and ATR parameters",
     ["EXP-0022", "H-0010", "P5-0001", "EXP-0006", "H-0019", "H-0020"], None,
     []),
    ("Shorting", ["EXP-0011", "EXP-0012", "EXP-0013", "EXP-0026", "H-0027",
                  "H-0028", "H-0029", "H-0030"], None,
     ["docs/2026-09-10-short-book-rejected.md",
      "docs/2026-10-03-shorting-and-all-in-report.md",
      "docs/2026-09-10-shorting-the-signal-rejected.md",
      "docs/2026-09-10-volatile-opens-rejected.md"]),
    ("News filters and news information",
     ["EXP-0040", "EXP-0041", "P5-0006", "P5-0011", "P5-0012", "P5-0013",
      "H-0022"], None, ["docs/2026-09-18-news-feasibility.md"]),
    ("Cross-sectional ranking / relative strength",
     ["EXP-0025", "H-0019"], "H-0019's cross-sectional branch is its P4 "
     "probe; the quotation on the H-0019 note is from that analysis.", []),
    ("Entry filters, liquidity/ATR opportunity branches and capacity",
     ["P5-0001", "P5-0002", "P5-0003", "P5-0004", "P5-0005", "H-0019",
      "H-0020", "H-0015", "H-0016", "EXP-0001", "EXP-0021", "EXP-0046",
      "H-0031"],
     None, ["docs/2026-09-17-breadth-forensics.md",
            "docs/2026-09-17-bucket-forensics.md",
            "docs/2026-09-11-position-count-rejected.md"]),
    ("Idle-cash deployment", ["EXP-0014", "EXP-0028", "H-0006"], None, []),
    ("Crypto", ["EXP-0003", "EXP-0015", "EXP-0032", "EXP-0033", "EXP-0034",
                "EXP-0035"], None, ["docs/2026-09-08-crypto-rejected.md"]),
    ("Learned model / ranking veto", ["EXP-0029"], None,
     ["docs/2026-09-12-the-learning-loop.md"]),
    ("Intraday, day trading and entry timing",
     ["EXP-0007", "EXP-0008", "EXP-0016", "EXP-0017", "EXP-0019", "H-0014",
      "H-0024", "H-0032", "H-0033", "H-0034", "H-0035", "H-0036"], None,
     ["2026-09-07-orb-rejected.md", "docs/2026-09-09-intraday-swings-rejected.md",
      "docs/2026-09-19-day-trading-research.md",
      "docs/2026-09-19-day-trading-deep-dive.md",
      "docs/2026-09-19-day-trading-part-iii.md",
      "docs/2026-10-03-day-trading-what-works.md",
      "docs/2026-10-04-what-else-day-traders-do.md",
      "docs/2026-10-04-day-trading-everything-else.md"]),
    ("Execution modelling, the haircut and limit exits",
     ["H-0008", "H-0011", "H-0012", "H-0013", "H-0017", "H-0018", "EXP-0039",
      "EXP-0048", "EXP-0030"], None,
     ["docs/2026-09-20-intraday-execution-measurement.md"]),
    ("Give-back / profit realisation", ["H-0021", "H-0025"], None, []),
    ("Survivorship and universe", ["EXP-0031", "H-0023"], None, []),
    ("Trend filter", ["EXP-0004", "EXP-0020"], None, []),
    ("Overnight selection", ["EXP-0005", "EXP-0010", "EXP-0018", "EXP-0027"],
     None, ["docs/2026-09-09-overnight-decomposition.md",
            "docs/2026-09-10-overnight-selection.md"]),
    ("Futures: diversified trend following", ["H-0039"], None,
     ["docs/2026-09-28-long-short-and-broker-research.md"]),
]

#: Existing documents whose role is fixed by what they declare themselves.
DOC_ROLE = {
    "docs/SPEC-0001-decision-boundary.md": "NORMATIVE SOURCE",
    "docs/phase3-forward-evaluation-protocol.md": "NORMATIVE SOURCE",
    "docs/phase4-clean-observation-protocol.md": "NORMATIVE SOURCE",
    "docs/benchmark-units.md": "BENCHMARK DEFINITION",
}
#: Documents with a verified statement that the frozen state contradicts.
DOC_SUPERSEDED = {
    "README.md": "states a next-open entry and a fixed target; superseded "
                 "by EXP-0016 and the frozen configuration",
    "START-HERE.md": "mentions a trailing stop line; the frozen strategy has "
                     "no trailing stop",
    "docs/GO-LIVE.md": "describes a long-only trend rule; the frozen "
                       "strategy is mean reversion",
    "docs/phase3-forward-evaluation-protocol.md":
        "its \"approximately 2026-10-09\" start date is corrected by the "
        "Phase 4 protocol §1",
}

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_text_cache = {}
_tracked = None


def tracked_files():
    """Repository paths git tracks. A link to anything else - an ignored cache,
    a local log - resolves on one machine and is broken for everyone else."""
    global _tracked
    if _tracked is None:
        import subprocess
        out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO,
                             capture_output=True, check=True).stdout
        _tracked = {p for p in out.decode("utf-8").split("\0") if p}
    return _tracked


def norm(text):
    """Collapse whitespace and drop Markdown emphasis/code marks."""
    return re.sub(r"\s+", " ", re.sub(r"[*`]", "", text)).strip()


def source_text(path):
    """Normalised searchable text of a repository file. JSONL is decoded, so
    a quotation matches the string a ledger row holds, not its escaping."""
    if path not in _text_cache:
        raw = (REPO / path).read_text(encoding="utf-8")
        if path.endswith(".jsonl"):
            parts = []

            def walk(v):
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, dict):
                    for x in v.values():
                        walk(x)
                elif isinstance(v, list):
                    for x in v:
                        walk(x)
            for line in raw.splitlines():
                if line.strip():
                    walk(json.loads(line))
            raw = "\n".join(parts)
        elif path.endswith((".py", ".ps1")):
            # A quotation from a comment may run over several comment lines;
            # the markers at the start of each line are not part of the words.
            raw = re.sub(r"\n[ \t]*#+[ \t]?", "\n", raw)
        elif path.endswith(".md"):
            raw = re.sub(r"\n[ \t]*>[ \t]?", "\n", raw)   # blockquote markers
        _text_cache[path] = norm(raw)
    return _text_cache[path]


def anchor_ok(path, quote):
    return norm(quote) in source_text(path)


def all_anchors():
    """Every (file, quotation) the generated notes rest on."""
    out = []
    for hid, c in CURATED.items():
        out.extend((hid, f, q) for f, q in c["quotes"])
    for hid, rows in FINDINGS.items():
        out.extend((hid + " finding", f, q) for _, f, q in rows)
    for a, b, _, f, q in RELATIONS:
        out.append((a + "->" + b, f, q))
    for k, (_, f, q) in SPEC_LINKS.items():
        out.append((k + " spec", f, q))
    return out


def cell(text, limit=None):
    s = re.sub(r"\s+", " ", str(text)).strip().replace("|", "\\|")
    if limit and len(s) > limit:
        s = s[:limit - 1].rstrip() + "…"
    return s


def link_to(note_path, repo_path, label=None):
    rel = os.path.relpath(REPO / repo_path, note_path.parent).replace("\\", "/")
    return "[{0}]({1})".format(label or repo_path, rel)


def frontmatter(**fields):
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, (list, tuple)):
            lines.append("{0}:".format(k))
            lines.extend("  - {0}".format(json.dumps(x, ensure_ascii=False))
                         for x in v)
        elif isinstance(v, bool):
            lines.append("{0}: {1}".format(k, "true" if v else "false"))
        else:
            lines.append("{0}: {1}".format(k, json.dumps(v, ensure_ascii=False)))
    lines.append("---")
    return "\n".join(lines)


WHAT = {
    "VALIDATED EVIDENCE": "a measurement that passed its registered controls "
                          "in-sample, on contaminated historical data - no "
                          "Clean OOS evidence exists yet. It validates the "
                          "stated measurement only - never a trading change "
                          "and never future performance",
    "MEASUREMENT": "a descriptive measurement with no accept/reject decision",
    "INCONCLUSIVE": "evidence that is insufficient for any production "
                    "conclusion",
    "REJECTED": "an idea rejected under its documented criteria. Rejected "
                "means what the row says was tested and what it showed - not "
                "that the idea is impossible",
    "OPEN QUESTION": "an unresolved question",
    "HISTORICAL": "point-in-time or superseded material kept for provenance",
}


def banner(authority):
    if authority in NOT_A_RULE:
        return ("> [!warning] {0}\n> Authority: **{1}**. This note records {2}. "
                "It does not describe, change or authorise any trading "
                "behaviour. What the bot does: [[Production Truth]]. What "
                "governs it: [[SPEC-0001]] and [[Frozen Strategy]].").format(
                    NOT_A_RULE_MARK, authority, WHAT[authority])
    if authority == "REMEDIATION":
        return ("> [!info] REMEDIATION RECORD\n> Records an implementation or "
                "governance correction that was made. It authorises no "
                "further change. The ledger row is the record; this note "
                "renders it.")
    if authority == "NORMATIVE":
        return ("> [!important] NORMATIVE — pointer note\n> The governing "
                "text is the linked source. This note indexes it; if the two "
                "ever differ, **the source governs**.")
    if authority == "FROZEN":
        return ("> [!note] FROZEN — the frozen strategy as implemented\n> "
                "Read from the linked sources at build time. If this note and "
                "a source differ, **the source governs**.")
    return ("> [!abstract] NAVIGATION — non-authoritative\n> Organises and "
            "links. Asserts nothing beyond its cited sources and never "
            "overrides them.")


GEN_NOTE = ("*Generated by `scripts/build_knowledge_base.py` from the governed "
            "ledgers. Edit the source, never this note.*")

# ---------------------------------------------------------------------------
# Ledger loading
# ---------------------------------------------------------------------------


def load_jsonl(path):
    rows = []
    for n, line in enumerate((REPO / path).read_text(encoding="utf-8")
                             .splitlines(), start=1):
        if line.strip():
            rows.append((n, json.loads(line)))
    return rows


class Ledgers:
    def __init__(self):
        self.exp = {r["id"]: (n, r) for n, r in load_jsonl(EXPERIMENTS)}
        self.p5 = {r["id"]: (n, r) for n, r in load_jsonl(PHASE5)}
        self.h = {r["payload"]["hypothesis_id"]: (n, r["payload"], r["digest"])
                  for n, r in load_jsonl(PREREG)}
        self.rem = {r["payload"]["id"]: (n, r["payload"], r["digest"])
                    for n, r in load_jsonl(REMEDIATIONS)}
        self.sealed_as = defaultdict(list)
        for pid, (_, r) in sorted(self.p5.items()):
            cfg = r.get("configuration")
            s = cfg.get("sealed_as") if isinstance(cfg, dict) else None
            if s:
                self.sealed_as[s].append(pid)
        # "RESULT for EXP-0040" pairs, read from the result row's own text.
        self.result_of, self.result_row = {}, {}
        for eid, (_, r) in self.exp.items():
            m = re.search(r"RESULT for (EXP-\d{4})", r["hypothesis"])
            if m:
                self.result_of[eid] = m.group(1)
                self.result_row[m.group(1)] = eid
        self.hids = sorted(set(self.h) | {"H-0022"})

    def exists(self, i):
        return (i in self.exp or i in self.p5 or i in self.h or i in self.rem
                or i == "H-0022")

    def authority(self, i):
        if i in CURATED:
            return CURATED[i]["authority"]
        if i in self.exp:
            return EXP_AUTHORITY[self.exp[i][1]["decision"]]
        if i in self.p5:
            return P5_AUTHORITY[self.p5[i][1]["verdict"]]
        if i in self.rem:
            return "REMEDIATION"
        raise KeyError(i)

    def status(self, i):
        """The item's recorded outcome, in the source's own words."""
        if i in CURATED:
            return CURATED[i]["quotes"][0][1]
        if i in self.exp:
            return self.exp[i][1]["decision"]
        if i in self.p5:
            return self.p5[i][1]["verdict"]
        if i in self.rem:
            return "recorded"
        raise KeyError(i)

    def title(self, i):
        if i in CURATED:
            return CURATED[i]["title"]
        if i in self.exp:
            return self.exp[i][1]["hypothesis"]
        if i in self.p5:
            return self.p5[i][1]["hypothesis"]
        if i in self.rem:
            return self.rem[i][1]["title"]
        raise KeyError(i)


def referenced_ids(text, own=None):
    return sorted({m for m in ID_RE.findall(text) if m != own})


def rems_mentioning(L, item):
    out = []
    for rid, (_, p, _) in sorted(L.rem.items()):
        if item in json.dumps(p, ensure_ascii=False):
            out.append(rid)
    return out


def wl(L, i):
    return "[[{0}]]".format(i) if L.exists(i) else "{0} (no such item)".format(i)


def freeze_facts():
    from event_aware_trader import purge, research
    reg = research.load_registry()
    return purge.freeze_date(reg), sorted(purge.CONFIG_CHANGING)

# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def registered_letter(payload, letter):
    """The registration's own definition of an outcome letter, verbatim."""
    text = norm(payload["acceptance_criteria"])
    m = re.search(r"\(" + letter + r"\)\s*(.+?)(?=\s\([A-E]\)\s|\sNo fifth|$)",
                  text)
    return m.group(1).strip() if m else None


def render_hypothesis(L, hid, freeze):
    path = KB / "03-research" / "hypotheses" / (hid + ".md")
    c = CURATED[hid]
    reg = L.h.get(hid)
    reports = H_REPORTS.get(hid, [])
    data_files = sorted(
        f for f in ("docs/phase5/" + p.name for p in (REPO / "docs" / "phase5")
                    .glob("h{0}-*.json".format(hid[2:])))
        if f in tracked_files())
    sources = ([PREREG] if reg else []) + reports + data_files
    if hid in L.sealed_as:
        sources.append(PHASE5)
    parts = [frontmatter(id=hid, title=c["title"], authority=c["authority"],
                         kind="hypothesis", registered=bool(reg),
                         generated=True, sources=sources),
             "", "# {0} — {1}".format(hid, c["title"]), "",
             banner(c["authority"]), "", GEN_NOTE, ""]
    if reg and uses_thirty_year("h", reg[1]):
        parts.append(thirty_year_caveat(path))

    parts.append("## Recorded outcome\n")
    for f, q in c["quotes"]:
        parts.append("- “{0}” — {1}".format(q, link_to(path, f)))
    parts.append("")
    parts.append("**Authority:** {0}. **Rule applied:** {1}.".format(
        c["authority"], c["rule"]))
    if c["letter"] and reg:
        d = registered_letter(reg[1], c["letter"])
        if d:
            parts.append("")
            parts.append("**Registered definition of outcome {0}:** “{1}”".format(
                c["letter"], cell(d, 420)))
    parts.append("")

    # Index record ------------------------------------------------------
    parts.append("## Index record\n")
    if reg:
        n, p, digest = reg
        parts += [
            "- **ID:** {0}".format(hid),
            "- **Title:** {0}".format(c["title"]),
            "- **Date:** {0} (registered_at)".format(p["registered_at"][:10]),
            "- **Status:** “{0}”".format(c["quotes"][0][1]),
            "- **Authority:** {0}".format(c["authority"]),
            "- **Hypothesis:** {0}".format(cell(p["statement"])),
            "- **Dataset:** {0}".format(cell("; ".join(p["datasets"]))),
            "- **Population:** UNVERIFIED — registrations carry no population "
            "field; see the report",
            "- **Validation method:** preregistered ({0}), seal `{1}`, code "
            "commit `{2}`, at most {3} configuration(s)".format(
                p["kind"], p["seal"][:16] + "…", p["code_commit"][:7],
                p["max_configurations"]),
            "- **Key result:** “{0}”".format(c["quotes"][0][1]),
            "- **Decision:** {0}".format(c["authority"]),
            "- **Production impact:** none. Registered {0}, after the "
            "research freeze of {1}; no config-changing experiment "
            "(`accepted`/`reverted`) has been recorded since "
            "(`purge.freeze_date`).".format(p["registered_at"][:10], freeze)
            if p["registered_at"][:10] > str(freeze) else
            "- **Production impact:** UNVERIFIED",
        ]
    else:
        parts += [
            "- **ID:** {0} — **UNREGISTERED** (no row in "
            "`docs/preregistrations.jsonl`)".format(hid),
            "- **Title:** {0}".format(c["title"]),
            "- **Date:** UNVERIFIED — no registration timestamp; the report "
            "file is dated 2026-09-22",
            "- **Status:** “{0}”".format(c["quotes"][-1][1]),
            "- **Authority:** {0}".format(c["authority"]),
            "- **Hypothesis:** UNVERIFIED — no sealed statement exists",
            "- **Dataset:** UNVERIFIED — see the report",
            "- **Population:** UNVERIFIED — see the report",
            "- **Validation method:** none registered — “No experiment "
            "registered.”",
            "- **Key result:** “{0}”".format(c["quotes"][-1][1]),
            "- **Decision:** {0} (unregistered)".format(c["authority"]),
            "- **Production impact:** none recorded; the research freeze "
            "remains {0}".format(freeze),
        ]
    execs = L.sealed_as.get(hid, [])
    parts.append("- **Related experiments:** {0}".format(
        ", ".join("[[{0}]]".format(x) for x in execs) +
        (" (phase-5 executions, by `configuration.sealed_as`)" if execs
         else "none recorded by `sealed_as`")))
    spec = SPEC_LINKS.get(hid)
    parts.append("- **Related specification clauses:** {0}".format(
        "[[SPEC-0001]] — {0}".format(spec[0]) if spec else "none recorded"))
    rems = rems_mentioning(L, hid)
    parts.append("- **Related remediation:** {0}".format(
        ", ".join("[[{0}]]".format(r) for r in rems) if rems
        else "none recorded"))
    loc = []
    if reg:
        loc.append(link_to(path, PREREG, "preregistrations.jsonl line "
                           + str(reg[0])))
    loc += [link_to(path, PHASE5, "phase5-research.jsonl line {0} ({1})"
                    .format(L.p5[x][0], x)) for x in execs]
    loc += [link_to(path, f) for f in reports + data_files]
    parts.append("- **Evidence location:** {0}".format(
        "; ".join(loc) if loc else "UNVERIFIED"))
    parts.append("")

    if hid in FINDINGS:
        parts.append("## Key findings (verbatim)\n")
        parts.append("*Each line is quoted exactly from its source and "
                     "checked at build time. The headings are navigation; "
                     "none of this is a recommendation.*\n")
        for label, f, q in FINDINGS[hid]:
            parts.append("- **{0}:** “{1}” — {2}".format(label, q,
                                                          link_to(path, f)))
        parts.append("")

    rel = [r for r in RELATIONS if r[0] == hid]
    if rel:
        parts.append("## Relationships stated by a source\n")
        for _, to, what, f, q in rel:
            parts.append("- {0} — {1}. Source: “{2}” — {3}".format(
                wl(L, to), what, q, link_to(path, f)))
        parts.append("")

    if execs:
        parts.append("## Phase-5 executions\n")
        parts.append("| ID | verdict | authority | configuration |")
        parts.append("|---|---|---|---|")
        for x in execs:
            r = L.p5[x][1]
            parts.append("| [[{0}]] | {1} | {2} | {3} |".format(
                x, r["verdict"], L.authority(x), cell(r["hypothesis"], 90)))
        parts.append("")

    ids = set()
    for f in reports:
        ids.update(referenced_ids((REPO / f).read_text(encoding="utf-8"), hid))
    if ids:
        parts.append("## Identifiers the report(s) mention\n")
        parts.append("*Mechanical: every ID that appears in the report text. "
                     "A mention is not a relationship.*\n")
        parts.append(", ".join(wl(L, i) for i in sorted(ids)))
        parts.append("")

    if reg:
        p = reg[1]
        parts.append("## Registration excerpts (verbatim)\n")
        parts.append("- **Primary metric:** {0}".format(
            cell(p["primary_metric"], 600)))
        parts.append("- **Information boundary:** {0}".format(
            cell(p["information_boundary"], 600)))
        parts.append("- **Rejection criteria:** {0}".format(
            cell(p["rejection_criteria"], 600)))
        parts.append("")
    return path, "\n".join(parts)


def render_experiment(L, eid):
    path = KB / "03-research" / "experiments" / (eid + ".md")
    n, r = L.exp[eid]
    auth = L.authority(eid)
    parts = [frontmatter(id=eid, title=cell(r["hypothesis"], 120),
                         authority=auth, kind="experiment", generated=True,
                         sources=[EXPERIMENTS]),
             "", "# {0} — {1}".format(eid, cell(r["hypothesis"], 110)), "",
             banner(auth), "", GEN_NOTE, ""]
    if eid in L.result_row:
        parts.append("> [!note] The result of this registration is recorded "
                     "in [[{0}]].\n".format(L.result_row[eid]))
    if eid in L.result_of:
        parts.append("> [!note] This row is the result of [[{0}]].\n".format(
            L.result_of[eid]))
    if r["when"] < "2026-09-16":
        parts.append("> [!caution] Measurement basis\n> [[EXP-0054]] "
                     "(2026-09-16) records: “Every figure published before "
                     "today was overstated by roughly 2.6 points.” — {0}. "
                     "This row is dated {1}.\n".format(
                         link_to(path, EXPERIMENTS), r["when"]))
    if uses_thirty_year("exp", r):
        parts.append(thirty_year_caveat(path))
    if r["decision"] in ("accepted",):
        parts.append("Adopted into the frozen configuration — see "
                     "[[Frozen Strategy]] and [[Production Truth]].\n")
    if r["decision"] == "reverted":
        parts.append("Adopted, then reverted — see the reason below.\n")

    parts.append("## Index record\n")
    parts += [
        "- **ID:** {0}".format(eid),
        "- **Title:** {0}".format(cell(r["hypothesis"])),
        "- **Date:** {0}".format(r["when"]),
        "- **Status:** {0} (ledger `decision`)".format(r["decision"]),
        "- **Authority:** {0}".format(auth),
        "- **Hypothesis:** {0}".format(cell(r["hypothesis"])),
        "- **Dataset:** {0}; contaminated: {1}".format(
            ", ".join(r["data_periods"]) or "none recorded",
            ", ".join(r["contaminated"]) or "none recorded"),
        "- **Population:** UNVERIFIED — `experiments.jsonl` has no "
        "population field",
        "- **Validation method:** {0} configuration(s); validation result: "
        "{1}; holdout result: {2}".format(
            r["configurations"],
            cell(r["validation_result"]) if r["validation_result"] is not None
            else "not recorded",
            cell(r["holdout_result"]) if r["holdout_result"] is not None
            else "not recorded"),
        "- **Key result:** {0}".format(cell(r["result"]) if r["result"]
                                       else "not recorded"),
        "- **Decision:** {0} — {1}".format(r["decision"], cell(r["reason"])),
        "- **Production impact:** {0}".format(
            "adopted into the shipped configuration (`accepted` is "
            "config-changing)" if r["decision"] == "accepted" else
            "adopted, then reverted (`reverted` is config-changing)"
            if r["decision"] == "reverted" else
            "none — `{0}` is not a config-changing decision "
            "(`purge.CONFIG_CHANGING` = accepted, reverted)".format(
                r["decision"])),
        "- **Related experiments:** {0}".format(
            ", ".join(wl(L, i) for i in referenced_ids(
                json.dumps(r, ensure_ascii=False), eid)) or "none named in "
            "the row") + "; `related_before` = {0}".format(r["related_before"]),
        "- **Related specification clauses:** none recorded",
        "- **Related remediation:** {0}".format(
            ", ".join("[[{0}]]".format(x) for x in rems_mentioning(L, eid))
            or "none recorded"),
        "- **Evidence location:** {0}; evidence grade in ledger: {1}".format(
            link_to(path, EXPERIMENTS, "experiments.jsonl line " + str(n)),
            r["evidence"]),
        "",
        "## Other ledger fields\n",
        "- **family:** {0}".format(r["family"]),
        "- **config:** `{0}`".format(cell(json.dumps(r["config"]), 300)),
        "- **parameters:** `{0}`".format(cell(json.dumps(r["parameters"]), 300)),
        "- **features:** `{0}`".format(cell(json.dumps(r["features"]), 300)),
        "- **trial_sharpes:** `{0}`".format(cell(json.dumps(r["trial_sharpes"]),
                                                 300)),
        "",
    ]
    return path, "\n".join(parts)


def render_p5(L, pid):
    path = KB / "03-research" / "phase5" / (pid + ".md")
    n, r = L.p5[pid]
    auth = L.authority(pid)
    cfg = r.get("configuration") if isinstance(r.get("configuration"), dict) else {}
    sealed = cfg.get("sealed_as")
    parts = [frontmatter(id=pid, title=cell(r["hypothesis"], 120),
                         authority=auth, kind="phase5-execution",
                         generated=True, sources=[PHASE5]),
             "", "# {0} — {1}".format(pid, cell(r["hypothesis"], 110)), "",
             banner(auth), "", GEN_NOTE, ""]
    if sealed:
        parts.append("Execution of the sealed hypothesis [[{0}]].\n".format(
            sealed))
    if uses_thirty_year("p5", r):
        parts.append(thirty_year_caveat(path))
    diff = r.get("difference_from_baseline") or {}
    parts.append("## Index record\n")
    parts += [
        "- **ID:** {0}".format(pid),
        "- **Title:** {0}".format(cell(r["hypothesis"])),
        "- **Date:** {0}".format(str(r["when"])[:10]),
        "- **Status:** {0} (ledger `verdict`)".format(r["verdict"]),
        "- **Authority:** {0}".format(auth),
        "- **Hypothesis:** {0}".format(cell(r["hypothesis"])),
        "- **Dataset:** {0}; date range {1}".format(cell(r["dataset"]),
                                                    cell(r["date_range"])),
        "- **Population:** {0}".format(cell(r["universe"])),
        "- **Validation method:** {0}".format(cell(r["validation_methodology"])),
        "- **Key result:** {0}".format(cell(r["conclusion"])),
        "- **Decision:** {0}".format(r["verdict"]),
        "- **Production impact:** none — phase-5 verdicts cannot accept "
        "anything: “nothing here can \"accept\" anything” — {0}".format(
            link_to(path, "src/event_aware_trader/phase5/ledger.py")),
        "- **Related experiments:** {0}".format(
            ", ".join(wl(L, i) for i in referenced_ids(
                json.dumps(r, ensure_ascii=False), pid)) or "none named"),
        "- **Related specification clauses:** none recorded",
        "- **Related remediation:** {0}".format(
            ", ".join("[[{0}]]".format(x) for x in rems_mentioning(L, pid))
            or "none recorded"),
        "- **Evidence location:** {0}".format(
            link_to(path, PHASE5, "phase5-research.jsonl line " + str(n))),
        "",
        "## Other ledger fields\n",
        "- **trials:** {0}".format(r["trials"]),
        "- **suitable_for_further_testing (ledger field, not an "
        "instruction):** {0}".format(r["suitable_for_further_testing"]),
        "- **execution assumptions:** {0}".format(
            cell(r["execution_assumptions"], 400)),
        "- **costs:** {0}".format(cell(r["costs"], 300)),
        "- **leakage risks:** {0}".format(cell("; ".join(
            r["leakage_risks"]) if isinstance(r["leakage_risks"], list)
            else r["leakage_risks"], 600)),
        "",
    ]
    if diff:
        parts.append("### Difference from baseline (ledger values)\n")
        parts.append("| metric | difference |")
        parts.append("|---|---:|")
        for k in sorted(diff):
            parts.append("| {0} | {1} |".format(k, diff[k]))
        parts.append("")
    return path, "\n".join(parts)


def render_rem(L, rid):
    path = KB / "04-remediation" / "records" / (rid + ".md")
    n, p, digest = L.rem[rid]
    parts = [frontmatter(id=rid, title=p["title"], authority="REMEDIATION",
                         kind="remediation", generated=True,
                         sources=[REMEDIATIONS]),
             "", "# {0} — {1}".format(rid, p["title"]), "",
             banner("REMEDIATION"), "", GEN_NOTE, ""]
    parts.append("## Index record\n")
    spec = SPEC_LINKS.get(rid)
    parts += [
        "- **ID:** {0}".format(rid),
        "- **Title:** {0}".format(cell(p["title"])),
        "- **Date:** {0}".format(str(p["when"])[:10]),
        "- **Status:** recorded in the hash-chained remediation ledger",
        "- **Authority:** REMEDIATION",
        "- **What was wrong:** {0}".format(cell(p["what_was_wrong"])),
        "- **Correction:** {0}".format(cell(p["correction"])),
        "- **Affects:** {0}".format(cell(p["affects"])),
        "- **Economic rules changed:** {0}".format(p["economic_rules_changed"]),
        "- **Fingerprint before → after:** `{0}` → `{1}`".format(
            str(p["fingerprint_before"])[:16] + "…",
            str(p["fingerprint_after"])[:16] + "…"),
        "- **Historical results usable:** {0}".format(
            cell(p["historical_results_usable"])),
        "- **Reports affected:** {0}".format(cell(p["reports_affected"])),
        "- **Related specification clauses:** {0}".format(
            "[[SPEC-0001]] — {0}".format(spec[0]) if spec else
            (cell(p["spec"]) if p.get("spec") else "none recorded")),
        "- **Related research items:** {0}".format(
            ", ".join(wl(L, i) for i in referenced_ids(
                json.dumps(p, ensure_ascii=False), rid)) or "none named"),
        "- **Evidence location:** {0}; chain digest `{1}`".format(
            link_to(path, REMEDIATIONS, "remediations.jsonl line " + str(n)),
            digest[:16] + "…"),
        "",
    ]
    extra = [k for k in ("evidence", "residual_non_conformance",
                         "money_path_review", "baseline", "clean_oos",
                         "effective_runtime_digest") if k in p]
    if extra:
        parts.append("## Further recorded fields\n")
        for k in extra:
            parts.append("- **{0}:** {1}".format(k, cell(p[k], 900)))
        parts.append("")
    return path, "\n".join(parts)


def render_index(L, freeze):
    path = KB / "03-research" / "Research Index.md"
    report_files = sorted({f for fs in H_REPORTS.values() for f in fs})
    parts = [frontmatter(title="Research Index", authority="NAVIGATION",
                         kind="index", generated=True,
                         sources=[PREREG, PHASE5, EXPERIMENTS, REMEDIATIONS]
                         + report_files),
             "", "# Research Index", "", banner("NAVIGATION"), "", GEN_NOTE,
             ""]
    parts.append(
        "Every item in the four governed ledgers, plus the one unregistered "
        "hypothesis-numbered audit (H-0022). Each ID links to a note holding "
        "its full index record — ID, title, date, status, hypothesis, "
        "dataset, population, validation method, key result, decision, "
        "production impact, related experiments, specification clauses, "
        "remediation and evidence location — with UNVERIFIED wherever the "
        "source does not record a field. Reports without a ledger ID are in "
        "[[Reports Catalogue]].\n")
    parts.append("| ledger | items |")
    parts.append("|---|---:|")
    parts.append("| registered hypotheses (`preregistrations.jsonl`) | {0} |"
                 .format(len(L.h)))
    parts.append("| unregistered hypothesis-numbered audit | 1 (H-0022) |")
    parts.append("| phase-5 executions (`phase5-research.jsonl`) | {0} |"
                 .format(len(L.p5)))
    parts.append("| experiments (`experiments.jsonl`) | {0} |".format(
        len(L.exp)))
    parts.append("| remediations (`remediations.jsonl`) | {0} |".format(
        len(L.rem)))
    parts.append("")
    parts.append("Research freeze (`purge.freeze_date`): **{0}**.\n".format(
        freeze))

    parts.append("## Hypotheses\n")
    parts.append("| ID | date | title | authority | recorded outcome (verbatim) |")
    parts.append("|---|---|---|---|---|")
    for hid in L.hids:
        reg = L.h.get(hid)
        date = reg[1]["registered_at"][:10] if reg else "unregistered"
        parts.append("| [[{0}]] | {1} | {2} | {3} | “{4}” |".format(
            hid, date, cell(CURATED[hid]["title"], 70),
            CURATED[hid]["authority"], cell(CURATED[hid]["quotes"][0][1], 90)))
    parts.append("")

    parts.append("## Phase-5 executions\n")
    parts.append("| ID | date | sealed as | verdict | authority | hypothesis |")
    parts.append("|---|---|---|---|---|---|")
    for pid in sorted(L.p5):
        r = L.p5[pid][1]
        cfg = r.get("configuration") if isinstance(r.get("configuration"),
                                                   dict) else {}
        s = cfg.get("sealed_as")
        parts.append("| [[{0}]] | {1} | {2} | {3} | {4} | {5} |".format(
            pid, str(r["when"])[:10], "[[{0}]]".format(s) if s else "—",
            r["verdict"], L.authority(pid), cell(r["hypothesis"], 80)))
    parts.append("")

    parts.append("## Experiments\n")
    parts.append("| ID | date | family | decision | authority | configs | "
                 "hypothesis |")
    parts.append("|---|---|---|---|---|---:|---|")
    for eid in sorted(L.exp):
        r = L.exp[eid][1]
        parts.append("| [[{0}]] | {1} | {2} | {3} | {4} | {5} | {6} |".format(
            eid, r["when"], r["family"], r["decision"], L.authority(eid),
            r["configurations"], cell(r["hypothesis"], 80)))
    parts.append("")
    parts.append("EXP-0053 does not exist: {0}. See [[Conflicts and "
                 "Ambiguities]].\n".format(KNOWN_ABSENT["EXP-0053"]))

    parts.append("## Remediations\n")
    parts.append("Full list with fields: [[Remediation Index]].\n")
    parts.append("| ID | date | title |")
    parts.append("|---|---|---|")
    for rid in sorted(L.rem):
        p = L.rem[rid][1]
        parts.append("| [[{0}]] | {1} | {2} |".format(
            rid, str(p["when"])[:10], cell(p["title"], 90)))
    parts.append("")
    return path, "\n".join(parts)


def render_rem_index(L):
    path = KB / "04-remediation" / "Remediation Index.md"
    parts = [frontmatter(title="Remediation Index", authority="NAVIGATION",
                         kind="index", generated=True, sources=[REMEDIATIONS]),
             "", "# Remediation Index", "", banner("NAVIGATION"), "",
             GEN_NOTE, ""]
    parts.append("Every row of `docs/remediations.jsonl`, the hash-chained "
                 "ledger of implementation and governance corrections. "
                 "`economic_rules_changed` is the ledger's own field.\n")
    parts.append("| ID | date | title | affects | economic rules changed | "
                 "fingerprint before = after |")
    parts.append("|---|---|---|---|---|---|")
    for rid in sorted(L.rem):
        p = L.rem[rid][1]
        parts.append("| [[{0}]] | {1} | {2} | {3} | {4} | {5} |".format(
            rid, str(p["when"])[:10], cell(p["title"], 70),
            cell(p["affects"], 70), p["economic_rules_changed"],
            p["fingerprint_before"] == p["fingerprint_after"]))
    parts.append("")
    parts.append("Remediation is **not** optimisation: see "
                 "[[Agent Instructions]] rules 10 and 11.\n")
    return path, "\n".join(parts)


def render_dnr(L):
    path = KB / "03-research" / "Do Not Re-Research.md"
    parts = [frontmatter(title="Do Not Re-Research", authority="NAVIGATION",
                         kind="map", generated=True,
                         sources=[EXPERIMENTS, PHASE5, PREREG] + sorted(
                             {f for fs in H_REPORTS.values() for f in fs}
                             | {d for a in AREAS for d in a[3]})),
             "", "# Do Not Re-Research", "", banner("NAVIGATION"), "",
             GEN_NOTE, ""]
    parts.append(
        "Areas this project has already investigated, with the items that "
        "did it. **Read the rows before proposing anything in these areas.**"
        "\n\nHow to read this page:\n\n"
        "- Each row is the ledger's own text: what was tested, how many "
        "configurations, and the recorded decision. The grouping into areas "
        "is a navigation choice; the outcomes are not reinterpreted.\n"
        "- **Rejected is not \"impossible\".** It means the stated "
        "configurations, on the stated data, failed the stated criteria. "
        "The data scope is listed per area; most of it is the survivorship-"
        "affected decade and thirty-year windows, both contaminated for the "
        "current candidate.\n"
        "- A new proposal in a listed area must show how it differs from "
        "every row, and carries the prior configurations into its "
        "multiple-testing burden. It still goes through preregistration — "
        "this page grants nothing.\n"
        "- Areas with **no** registered test say so explicitly.\n")
    for name, ids, note, docs in AREAS:
        parts.append("## {0}\n".format(name))
        if note:
            parts.append("> [!note]\n> {0}\n".format(note))
        parts.append("| ID | authority | recorded outcome | configs | what "
                     "was tested |")
        parts.append("|---|---|---|---:|---|")
        scope = set()
        for i in ids:
            if i in L.exp:
                r = L.exp[i][1]
                cfgs = r["configurations"]
                outcome = "{0} — {1}".format(r["decision"],
                                             cell(r["result"] or r["reason"],
                                                  150))
                tested = r["hypothesis"]
                scope.update(r["data_periods"])
            elif i in L.p5:
                r = L.p5[i][1]
                cfgs = r["trials"]
                outcome = "{0} — {1}".format(r["verdict"],
                                             cell(r["conclusion"], 150))
                tested = r["hypothesis"]
                scope.add(cell(r["dataset"], 60))
            elif i in CURATED:
                reg = L.h.get(i)
                cfgs = reg[1]["max_configurations"] if reg else "—"
                outcome = "“{0}”".format(cell(CURATED[i]["quotes"][0][1], 150))
                tested = reg[1]["statement"] if reg else CURATED[i]["title"]
                if reg:
                    scope.update(cell(d, 60) for d in reg[1]["datasets"])
            else:
                raise KeyError(i)
            parts.append("| [[{0}]] | {1} | {2} | {3} | {4} |".format(
                i, L.authority(i), cell(outcome, 170), cfgs, cell(tested, 150)))
        parts.append("")
        if scope:
            parts.append("*Data scope recorded by these items:* {0}\n".format(
                "; ".join(sorted(scope))))
        if docs:
            parts.append("*Reports without a ledger ID:* {0}\n".format(
                ", ".join(link_to(path, d) for d in docs)))
    return path, "\n".join(parts)


def render_spec_clauses():
    path = KB / "01-frozen" / "SPEC-0001 Clauses.md"
    lines = (REPO / SPEC).read_text(encoding="utf-8").splitlines()
    section, rows = "", []
    for n, line in enumerate(lines, start=1):
        if line.startswith("#"):
            section = line.lstrip("#").strip()
        m = re.match(r"^\s*>?\s*\*\*C-(\d+)\.", line)
        if m:
            body = [line]
            k = n
            while k < len(lines) and lines[k].strip() and not re.match(
                    r"^\s*>?\s*\*\*C-\d+\.", lines[k]):
                body.append(lines[k])
                k += 1
            text = norm(re.sub(r"^\s*>\s?", "", " ".join(body)))
            text = re.sub(r"^C-\d+\.\s*", "", text)
            rows.append((int(m.group(1)), n, section, text))
    parts = [frontmatter(title="SPEC-0001 Clauses", authority="NORMATIVE",
                         kind="specification-index", generated=True,
                         sources=[SPEC]),
             "", "# SPEC-0001 Clauses", "", banner("NORMATIVE"), "", GEN_NOTE,
             ""]
    parts.append("Every clause of {0}, located by line, with its opening "
                 "words. **Read the clause in the source before relying on "
                 "it** — the opening words are an index, not the clause."
                 "\n".format(link_to(path, SPEC)))
    parts.append("| clause | line | section | opening words |")
    parts.append("|---|---:|---|---|")
    for cid, n, sec, text in sorted(rows):
        parts.append("| C-{0} | {1} | {2} | {3} |".format(
            cid, n, cell(sec, 60), cell(text, 150)))
    parts.append("")
    parts.append("Clauses found: **{0}** (C-{1} … C-{2}).\n".format(
        len(rows), min(r[0] for r in rows), max(r[0] for r in rows)))
    return path, "\n".join(parts), [r[0] for r in rows]


def decl_line(path, name, quoted=False):
    pat = (r'^\s*"{0}"\s*:' if quoted else r"^\s*{0}\s*[:=]").format(
        re.escape(name))
    for n, line in enumerate((REPO / path).read_text(encoding="utf-8")
                             .splitlines(), start=1):
        if re.match(pat, line):
            return n
    return None


def render_frozen_parameters():
    from event_aware_trader.autotrade import AutoTradeConfig
    from event_aware_trader.forward import frozen_fingerprint
    from event_aware_trader.live_model import LEARNED_RANKING_ENABLED
    from event_aware_trader.mean_reversion import MeanReversionConfig
    from event_aware_trader.purge import embargo_sessions
    from event_aware_trader.research import (CostModel, PRODUCTION_CANDIDATE,
                                             production_policy)
    from event_aware_trader.strategy import DEFAULT_UNIVERSE

    path = KB / "01-frozen" / "Frozen Parameters.md"
    mr_file = "src/event_aware_trader/mean_reversion.py"
    risk_file = "src/event_aware_trader/risk.py"
    cost_file = "src/event_aware_trader/costs.py"
    res_file = "src/event_aware_trader/research.py"
    at_file = "src/event_aware_trader/autotrade.py"
    cost_src = Path(sys.modules[CostModel.__module__].__file__)
    cost_file = cost_src.relative_to(REPO).as_posix()

    def table(title, file, obj_fields, quoted=False, note=None, defaults=None):
        out = ["## {0}\n".format(title)]
        if note:
            out.append(note + "\n")
        out.append("Declared in {0}. *line* is the field's declaration."
                   "\n".format(link_to(path, file)))
        out.append("| field | value | line |")
        out.append("|---|---|---:|")
        for k, v in obj_fields:
            ln = decl_line(file, k, quoted)
            shown = "`{0}`".format(cell(repr(v), 80))
            if defaults is not None and defaults.get(k) != v:
                shown += " (class default `{0}`, overridden)".format(
                    cell(repr(defaults.get(k)), 40))
            out.append("| `{0}` | {1} | {2} |".format(
                k, shown, ln if ln else "UNVERIFIED"))
        out.append("")
        return out

    def line_of(file, needle):
        for n, line in enumerate((REPO / file).read_text(encoding="utf-8")
                                 .splitlines(), start=1):
            if needle in line:
                return n
        return None

    at = AutoTradeConfig()
    fp_fields = ("entry_rule", "entry_window_minutes", "max_orders_per_run",
                 "cash_parking_symbol", "cash_parking_floor",
                 "reserved_fraction", "live_model_floor", "interval")
    live_extra = ("require_broker_side_stop", "require_market_open",
                  "dry_run", "asset_class", "period")
    eq = [s for s in DEFAULT_UNIVERSE if "/" not in s]
    cr = [s for s in DEFAULT_UNIVERSE if "/" in s]
    fp = frozen_fingerprint()
    sources = [mr_file, risk_file, cost_file, res_file, at_file,
               "src/event_aware_trader/forward.py",
               "src/event_aware_trader/live_model.py",
               "src/event_aware_trader/purge.py",
               "src/event_aware_trader/strategy.py"]
    parts = [frontmatter(title="Frozen Parameters", authority="FROZEN",
                         kind="configuration", generated=True,
                         sources=sources),
             "", "# Frozen Parameters", "", banner("FROZEN"), "", GEN_NOTE,
             "",
             "Read from the configuration objects themselves at build time — "
             "not from any report. Line numbers are where each field is "
             "declared. `scripts/validate_knowledge_base.py` regenerates this "
             "note and fails if it no longer matches the code.\n",
             "**Frozen fingerprint:** `{0}` — [[Frozen Fingerprint]].\n".format(
                 fp)]
    parts += table("Entry and exit rule — `MeanReversionConfig()`", mr_file,
                   dataclasses.asdict(MeanReversionConfig()).items())
    from event_aware_trader.risk import RiskPolicy
    parts += table("Risk and sizing — `research.production_policy()`",
                   risk_file, dataclasses.asdict(production_policy()).items(),
                   defaults=dataclasses.asdict(RiskPolicy()),
                   note="`production_policy()` is `RiskPolicy()` with "
                        "`allow_fractional_shares=False`. The live loop takes "
                        "`RiskPolicy()` and applies the same override for "
                        "sizing at `autotrade.py` line {0}.".format(
                            line_of(at_file,
                                    "replace(policy, allow_fractional_shares"
                                    "=False)")))
    parts += table("Cost model — `CostModel()`", cost_file,
                   dataclasses.asdict(CostModel()).items())
    parts += table("Production candidate — `research.PRODUCTION_CANDIDATE`",
                   res_file, PRODUCTION_CANDIDATE.items(), quoted=True,
                   note="Exactly {0} keys. No take-profit, trailing, partial, "
                        "momentum, regime or limit-exit key is present."
                        .format(len(PRODUCTION_CANDIDATE)))
    parts += table("Live settings covered by the fingerprint — "
                   "`AutoTradeConfig()`", at_file,
                   [(k, getattr(at, k)) for k in fp_fields])
    parts += table("Live settings NOT covered by the fingerprint — "
                   "`AutoTradeConfig()`", at_file,
                   [(k, getattr(at, k)) for k in live_extra],
                   note="`dry_run` is the class default; live sessions pass "
                        "`--live` (see [[Production Truth]]).")
    parts.append("## Other frozen facts\n")
    parts.append("| fact | value | source |")
    parts.append("|---|---|---|")
    parts.append("| `LEARNED_RANKING_ENABLED` | `{0}` | {1} line {2} |".format(
        LEARNED_RANKING_ENABLED,
        link_to(path, "src/event_aware_trader/live_model.py"),
        decl_line("src/event_aware_trader/live_model.py",
                  "LEARNED_RANKING_ENABLED")))
    parts.append("| embargo (`purge.embargo_sessions()`) | {0} sessions | {1} "
                 "|".format(embargo_sessions(),
                            link_to(path, "src/event_aware_trader/purge.py")))
    parts.append("| universe (`strategy.DEFAULT_UNIVERSE`) | {0} symbols: {1} "
                 "equity/ETF, {2} crypto pairs | {3} |".format(
                     len(DEFAULT_UNIVERSE), len(eq), len(cr),
                     link_to(path, "src/event_aware_trader/strategy.py")))
    parts.append("")
    return path, "\n".join(parts)


def doc_title(path):
    for line in (REPO / path).read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return "(untitled)"


def all_docs():
    out = [p.relative_to(REPO).as_posix() for p in sorted(REPO.glob("*.md"))]
    out += [p.relative_to(REPO).as_posix()
            for p in sorted((REPO / "docs").glob("*.md"))]
    return out


def render_catalogue(L):
    path = KB / "07-sources" / "Reports Catalogue.md"
    report_of = {}
    for hid, fs in H_REPORTS.items():
        for f in fs:
            report_of.setdefault(f, []).append(hid)
    docs = all_docs()
    parts = [frontmatter(title="Reports Catalogue", authority="NAVIGATION",
                         kind="catalogue", generated=True, sources=docs),
             "", "# Reports Catalogue", "", banner("NAVIGATION"), "",
             GEN_NOTE, ""]
    parts.append(
        "Every Markdown document in the repository outside `knowledge/`, "
        "classified by **role** (what the document is) and **currency** "
        "(whether its statements can be read as current). This page does "
        "not copy or rewrite any document.\n\n"
        "- **Role** is taken from the document's own declaration "
        "(NORMATIVE SOURCE, BENCHMARK DEFINITION), from being the report of "
        "a ledger item (LEDGER-LINKED REPORT), or from its dated filename "
        "(DATED REPORT). Anything else is GUIDE / REFERENCE.\n"
        "- **Currency:** a dated report is POINT-IN-TIME — true as of its "
        "date, and later work may supersede it. SUPERSEDED IN PART is used "
        "only where a specific statement was verified against the frozen "
        "state; the conflict is recorded in [[Conflicts and Ambiguities]]. "
        "Where currency could not be verified it is marked UNVERIFIED.\n")
    parts.append("| document | title | role | currency | report of | IDs "
                 "mentioned |")
    parts.append("|---|---|---|---|---|---:|")
    for d in docs:
        m = re.match(r"(?:docs/)?(\d{4}-\d{2}-\d{2})-", d)
        date = m.group(1) if m else None
        role = DOC_ROLE.get(d) or ("LEDGER-LINKED REPORT" if d in report_of
                                   else "DATED REPORT" if date
                                   else "GUIDE / REFERENCE")
        if d in DOC_SUPERSEDED:
            currency = "SUPERSEDED IN PART — " + DOC_SUPERSEDED[d]
        elif role in ("NORMATIVE SOURCE", "BENCHMARK DEFINITION"):
            currency = "CURRENT — governing"
        elif date:
            currency = "POINT-IN-TIME ({0})".format(date)
        else:
            currency = "UNVERIFIED"
        ids = referenced_ids((REPO / d).read_text(encoding="utf-8"))
        parts.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
            link_to(path, d, d), cell(doc_title(d), 70), role,
            cell(currency, 120),
            ", ".join("[[{0}]]".format(h) for h in report_of.get(d, []))
            or "—", len(ids)))
    parts.append("")
    parts.append("Documents catalogued: **{0}**.\n".format(len(docs)))
    return path, "\n".join(parts)

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build():
    """Return {path: text} for every generated note. Writes nothing."""
    bad = [(k, f, q) for k, f, q in all_anchors() if not anchor_ok(f, q)]
    if bad:
        for k, f, q in bad:
            print("ANCHOR NOT FOUND  {0}  {1}: {2!r}".format(k, f, q))
        raise SystemExit("REFUSED: curated quotations do not match their "
                         "sources. Nothing written.")
    L = Ledgers()
    missing = sorted(set(L.h) - set(CURATED))
    if missing:
        raise SystemExit("REFUSED: registered hypotheses without a curated "
                         "outcome: {0}".format(missing))
    for i in (L.exp, L.p5):
        for k, (_, r) in i.items():
            key = r.get("decision") or r.get("verdict")
            if key not in EXP_AUTHORITY and key not in P5_AUTHORITY:
                raise SystemExit("REFUSED: unknown decision {0!r} on {1}"
                                 .format(key, k))
    for name, ids, _, docs in AREAS:
        for i in ids:
            if not L.exists(i):
                raise SystemExit("REFUSED: area {0!r} names {1}, which does "
                                 "not exist".format(name, i))
        for d in docs:
            if not (REPO / d).exists():
                raise SystemExit("REFUSED: area {0!r} names missing file {1}"
                                 .format(name, d))
    freeze, _ = freeze_facts()
    out = {}
    for hid in L.hids:
        p, t = render_hypothesis(L, hid, freeze)
        out[p] = t
    for eid in sorted(L.exp):
        p, t = render_experiment(L, eid)
        out[p] = t
    for pid in sorted(L.p5):
        p, t = render_p5(L, pid)
        out[p] = t
    for rid in sorted(L.rem):
        p, t = render_rem(L, rid)
        out[p] = t
    for fn in (render_index,):
        p, t = fn(L, freeze)
        out[p] = t
    for fn in (render_rem_index, render_dnr, render_catalogue):
        p, t = fn(L)
        out[p] = t
    p, t, _ = render_spec_clauses()
    out[p] = t
    p, t = render_frozen_parameters()
    out[p] = t
    return {k: v.rstrip("\n") + "\n" for k, v in out.items()}


def is_generated(path):
    head = path.read_text(encoding="utf-8").split("---", 2)
    return len(head) > 2 and "\ngenerated: true" in head[1]


def main():
    check = "--check" in sys.argv
    notes = build()
    stale, clobber = [], []
    for p, text in sorted(notes.items()):
        if p.exists() and not is_generated(p):
            clobber.append(p)
        elif not p.exists() or p.read_text(encoding="utf-8") != text:
            stale.append(p)
    if clobber:
        for p in clobber:
            print("REFUSED: would overwrite hand-written note", p)
        return 2
    # A generated note that the ledgers no longer produce is orphaned.
    orphans = [p for p in KB.rglob("*.md") if p not in notes and is_generated(p)]
    if check:
        for p in stale:
            print("STALE  ", p.relative_to(REPO))
        for p in orphans:
            print("ORPHAN ", p.relative_to(REPO))
        print("{0} generated notes; {1} stale; {2} orphaned".format(
            len(notes), len(stale), len(orphans)))
        return 1 if (stale or orphans) else 0
    for p in stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(notes[p], encoding="utf-8", newline="\n")
    for p in orphans:
        print("ORPHANED generated note (not deleted - review it):",
              p.relative_to(REPO))
    print("wrote {0} of {1} generated notes; {2} anchors verified".format(
        len(stale), len(notes), len(all_anchors())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
