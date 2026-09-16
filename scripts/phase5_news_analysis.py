"""Phase 5 §4. Does the news that was public before the decision separate
the frozen strategy's good trades from its bad ones?

A screening test, and deliberately the cheap one first. If news carries no
separation across the trades the strategy actually took, there is nothing
to gain from the far more expensive portfolio re-run, and saying so is a
result. If it does separate, the separation still has to survive being
turned into a filter and re-run with capital reallocation - which is a
different and harder question this script does not answer.

What is NOT done here: no sentiment model is invented and no score is
declared useful. Two classifiers run side by side and each is reported as
what it is. `events.classify_headline` is the project's MACRO matcher and
answers whether a story was about rates, inflation or geopolitics; asked
whether a story was bad for one company it returns neutral, so it is used
only for its category. `phase5.headline` is an explicit equity keyword
list - headline text only, no article body, crude negation handling - and
exists so the question can be asked at all. Both are allowed to find
nothing, and finding nothing is a reportable result.

  python scripts/phase5_news_analysis.py deep
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.events import classify_headline        # noqa: E402
from event_aware_trader.phase5.headline import label, summarise  # noqa: E402
from event_aware_trader.phase5.asof import (                   # noqa: E402
    TIER2, Archive, decision_timestamp, quality_report)
from event_aware_trader.phase5.features import (               # noqa: E402
    TradeAnatomy, bucket, split_by, split_by_flag)

LOOKBACK_HOURS = 72.0


def show(title, buckets):
    print("\n  {0}".format(title))
    print("    {0:<38} {1:>5} {2:>11} {3:>9} {4:>8} {5:>7}".format(
        "bucket", "n", "P&L", "median R", "win%", "stop%"))
    for b in buckets:
        if not b.trades:
            continue
        print("    {0:<38} {1:>5} {2:>11,.0f} {3:>9} {4:>8} {5:>7}".format(
            b.label, b.trades, b.total_pnl,
            "-" if b.median_r is None else "{0:+.3f}".format(b.median_r),
            "-" if b.win_rate is None else "{0:.1%}".format(b.win_rate),
            "-" if b.stop_rate is None else "{0:.1%}".format(b.stop_rate)))


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    anatomy = REPO / "data" / "phase5" / "anatomy-{0}.jsonl".format(which)
    archive_path = REPO / "data" / "phase5" / "news-archive-{0}.jsonl".format(which)
    rows = [TradeAnatomy(**json.loads(l)) for l in
            anatomy.read_text(encoding="utf-8").splitlines() if l.strip()]
    archive = Archive.load(archive_path)

    print("ARCHIVE COVERAGE")
    for key, value in archive.coverage().items():
        print("  {0:<16} {1}".format(key, value))

    print("\nINFORMATION-QUALITY QUESTIONS (§12)")
    for question, answer in quality_report(archive).items():
        print("  {0:<34} {1}".format(question, answer["answer"]))
        print("      {0}".format(answer["detail"]))

    # ---- attach a decision-time snapshot to every trade -------------------
    enriched = []
    with_any = 0
    for row in rows:
        day = datetime.fromisoformat(row.entry_date).date()
        moment = decision_timestamp(day)
        snap = archive.snapshot(moment, [row.symbol],
                                lookback_hours=LOOKBACK_HOURS)
        items = snap.items
        if items:
            with_any += 1
        # Two classifiers, deliberately. The macro one answers "was this a
        # rate or geopolitics story"; it cannot answer "was this bad for
        # this company" and returns neutral if asked. The equity keyword
        # matcher answers the second question and nothing else.
        counts = summarise([i.headline for i in items])
        categories = defaultdict(int)
        for item in items:
            categories[classify_headline(item.headline).category] += 1
        enriched.append({
            "row": row,
            "items": len(items),
            "tier2": snap.count(maximum_tier=TIER2),
            "clean": snap.count(exclude_revised=True, max_symbols=5),
            "hours_since": snap.hours_since_newest(),
            "adverse": counts["adverse"],
            "favourable": counts["favourable"],
            "matched": counts["matched"],
            "earnings": categories.get("earnings", 0),
            "net_stance": counts["net"],
        })

    print("\nATTACHMENT")
    print("  trades                         {0}".format(len(rows)))
    print("  trades with any prior item     {0} ({1:.1%})".format(
        with_any, with_any / len(rows) if rows else 0))
    print("  lookback                       {0:.0f} hours before the decision"
          .format(LOOKBACK_HOURS))

    def sub(predicate, label):
        return bucket([e["row"] for e in enriched if predicate(e)], label)

    print("\nSEPARATION")
    show("any news in the 72h before the decision", [
        sub(lambda e: e["items"] == 0, "no prior item"),
        sub(lambda e: e["items"] > 0, "at least one prior item")])
    show("how much news", [
        sub(lambda e: e["items"] == 0, "0 items"),
        sub(lambda e: 1 <= e["items"] <= 2, "1-2 items"),
        sub(lambda e: 3 <= e["items"] <= 6, "3-6 items"),
        sub(lambda e: e["items"] >= 7, "7+ items")])
    show("tightly-tagged, unrevised items only", [
        sub(lambda e: e["clean"] == 0, "0 clean items"),
        sub(lambda e: 1 <= e["clean"] <= 2, "1-2 clean items"),
        sub(lambda e: e["clean"] >= 3, "3+ clean items")])
    show("equity keyword direction (headline only)", [
        sub(lambda e: e["items"] == 0, "no news"),
        sub(lambda e: e["items"] > 0 and e["matched"] == 0, "news, no keyword hit"),
        sub(lambda e: e["net_stance"] < 0, "net adverse"),
        sub(lambda e: e["matched"] > 0 and e["net_stance"] == 0, "balanced"),
        sub(lambda e: e["net_stance"] > 0, "net favourable")])
    show("any adverse headline at all", [
        sub(lambda e: e["adverse"] == 0, "no adverse headline"),
        sub(lambda e: e["adverse"] > 0, "at least one adverse headline")])
    show("an earnings headline in the window", [
        sub(lambda e: e["earnings"] == 0, "no earnings headline"),
        sub(lambda e: e["earnings"] > 0, "earnings headline present")])
    show("freshness of the newest item", [
        sub(lambda e: e["hours_since"] is None, "no item"),
        sub(lambda e: e["hours_since"] is not None and e["hours_since"] <= 6,
            "newest within 6h"),
        sub(lambda e: e["hours_since"] is not None and 6 < e["hours_since"] <= 24,
            "newest 6-24h"),
        sub(lambda e: e["hours_since"] is not None and e["hours_since"] > 24,
            "newest older than 24h")])

    out = REPO / "data" / "phase5" / "news-features-{0}.jsonl".format(which)
    out.write_text("".join(json.dumps(
        {k: v for k, v in dict(e, row=None).items() if k != "row"} |
        {"symbol": e["row"].symbol, "entry_date": e["row"].entry_date,
         "r_multiple": e["row"].r_multiple, "net_pnl": e["row"].net_pnl,
         "exit_reason": e["row"].exit_reason},
        sort_keys=True) + "\n" for e in enriched), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
