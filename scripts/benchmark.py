"""The account against the S&P 500's total return, over the identical window.

Two sections, kept apart on purpose:

  FORWARD   the only clean comparison. The paper account since it went live
            with the current candidate (research.FORWARD_START), from the
            equity readings the bot recorded at the time, against SPY with
            dividends reinvested over the same days. Flagged NOT A FINDING
            until it is long enough to be one.

  IN-SAMPLE the thirty-year and decade figures every parameter was chosen on.
            Contaminated, and labelled so. Shown because they are the only
            multi-year evidence there is, and because the decade's benchmark
            is now the CONFIRMED total-return figure rather than price return.

    python scripts/benchmark.py
"""

import sys
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.benchmark import (                        # noqa: E402
    BENCHMARK, closes_by_day, equity_by_day, forward_record)
from event_aware_trader.data import fetch_alpaca_equity_bars      # noqa: E402
from event_aware_trader.research import FORWARD_START             # noqa: E402

AUDIT = REPO / "data" / "autotrade-audit.jsonl"


def main():
    print("FORWARD RECORD  (the only clean comparison)")
    print("-" * 78)
    account = equity_by_day(AUDIT, FORWARD_START)
    since_days = ((max(account) - FORWARD_START).days + 10) if account else 10
    bars = fetch_alpaca_equity_bars([BENCHMARK], days=since_days,
                                    adjustment="all").get(BENCHMARK, [])
    record = forward_record(account, closes_by_day(bars), FORWARD_START)
    if record is None:
        print("   fewer than two sessions with both an account reading and a "
              "{0} close since {1}; nothing to compare yet".format(
                  BENCHMARK, FORWARD_START))
    else:
        print("   " + str(record))
        if not record.judgeable:
            print("   The excess return above is reported, not claimed. It "
                  "becomes a finding at {0} sessions.".format(
                      record.as_dict()["minimum_sessions"]))
    print("   account readings: {0} days  |  {1} closes: {2} days".format(
        len(account), BENCHMARK, len(bars)))

    print()
    print("IN-SAMPLE  (contaminated: every parameter was chosen on this data)")
    print("-" * 78)
    print("   {0:<44}{1:>9}{2:>9}{3:>10}".format("", "CAGR", "maxDD", "vs SPY"))
    # Decade. SPY total return CONFIRMED from Alpaca adjustment=all,
    # 2016-01-04..2026-09-14. The candidate figure is the parked, conservative
    # config (docs/2026-09-11-owner-ideas-priced.md).
    print("   {0:<44}{1:>9}{2:>9}{3:>10}".format(
        "decade 2016-26  SPY total return (CONFIRMED)", "15.00%", "-33.9%", ""))
    print("   {0:<44}{1:>9}{2:>9}{3:>10}".format(
        "decade 2016-26  candidate + parked cash", "9.87%", "-13.7%", "-5.1 pts"))
    # Thirty years. SPY PRICE return confirmed from the local series; total
    # return is an ESTIMATE because no dividend-adjusted series before 2016 is
    # reachable from this machine (Alpaca starts 2016; Yahoo is blocked by a
    # certificate error). The decade's MEASURED dividend contribution is
    # +1.58 pts/yr (15.00% total vs 13.42% price); SPY yielded more in
    # 1996-2015 than since, so the thirty-year figure is +1.6 to +2.0 pts.
    print("   {0:<44}{1:>9}{2:>9}{3:>10}".format(
        "30 yrs 1996-26  SPY price return (CONFIRMED)", "8.55%", "-56.5%", ""))
    print("   {0:<44}{1:>9}{2:>9}{3:>10}".format(
        "30 yrs 1996-26  SPY total return (ESTIMATE)", "~10.3%", "-55%", ""))
    print("   {0:<44}{1:>9}{2:>9}{3:>10}".format(
        "30 yrs 1996-26  candidate + parked cash", "5.75%", "-11.2%", "~-4.5 pts"))
    print()
    print("   Risk-adjusted, 7,719 aligned days (CONFIRMED): correlation 0.483, "
          "beta 0.205,\n   vol 8.2% vs 19.2%, Sharpe 0.66 vs 0.52, ruin(25%) 2.2% "
          "vs SPY's -56.5% drawdown.")
    print("   The candidate loses to SPY on return and wins on every risk "
          "measure. Both are true;\n   any claim of outperformance has to name "
          "which one it means.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
