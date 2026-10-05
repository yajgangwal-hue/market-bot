"""The account against the S&P 500's total return, over the identical window.

Two sections, kept apart on purpose:

  FORWARD   Clean OOS only. The window starts at the first session of the
            Phase 4 clean record - never at research.FORWARD_START, because
            the 20 embargo sessions after the freeze are paper-operational,
            not Clean OOS - and the paper account's equity readings are
            compared with SPY, dividends reinvested, over the same days.
            NOTHING is reported until the clean record holds
            MINIMUM_SESSIONS (60) sessions: the first performance report is
            Phase 4 checkpoint C, and an earlier number is an early look.
            Refuses if the clean record's chain is not intact.
            (Guard added 2026-09-24; comparison method unchanged:
            docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md)

  IN-SAMPLE the thirty-year and decade figures every parameter was chosen on.
            Contaminated, and labelled so. Shown because they are the only
            multi-year evidence there is, and because the decade's benchmark
            is now the CONFIRMED total-return figure rather than price return.

    python scripts/benchmark.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.benchmark import (                        # noqa: E402
    BENCHMARK, MINIMUM_SESSIONS, closes_by_day, equity_by_day, forward_record)
from event_aware_trader.forward import load_sessions, verify_chain  # noqa: E402
from event_aware_trader.data import fetch_alpaca_equity_bars      # noqa: E402

AUDIT = REPO / "data" / "autotrade-audit.jsonl"


class ForwardWindowRefused(RuntimeError):
    """The Clean OOS window cannot be established without ambiguity."""


def clean_window():
    """(first clean session, number of clean sessions) from the Phase 4 record.

    The clean record is the only authority on which sessions are Clean OOS:
    the recorder refuses every embargoed session and never backfills. A
    chain that does not verify is refused rather than read.
    """
    chain = verify_chain()
    if not chain.get("intact"):
        raise ForwardWindowRefused(
            "the clean record's chain is not intact: {0}".format(chain))
    sessions = load_sessions()
    if not sessions:
        return None, 0
    return date.fromisoformat(sessions[0].session), len(sessions)


def forward_section():
    print("FORWARD RECORD  (Clean OOS only - window set by the Phase 4 "
          "clean record)")
    print("-" * 78)
    first, count = clean_window()
    if first is None:
        print("   0 clean sessions recorded. Paper-account readings before the "
              "first clean session are paper-operational, not Clean OOS, and "
              "are not reported here.")
        return None
    if count < MINIMUM_SESSIONS:
        print("   {0} clean session(s) recorded from {1}. Nothing is reported "
              "below {2}: the first performance report is Phase 4 checkpoint "
              "C (scripts/phase4_checkpoint.py).".format(
                  count, first, MINIMUM_SESSIONS))
        return None
    account = equity_by_day(AUDIT, first)
    since_days = ((max(account) - first).days + 10) if account else 10
    bars = fetch_alpaca_equity_bars([BENCHMARK], days=since_days,
                                    adjustment="all").get(BENCHMARK, [])
    record = forward_record(account, closes_by_day(bars), first)
    if record is None:
        print("   fewer than two sessions with both an account reading and a "
              "{0} close since {1}; nothing to compare yet".format(
                  BENCHMARK, first))
    else:
        print("   " + str(record))
        if not record.judgeable:
            print("   The excess return above is reported, not claimed. It "
                  "becomes a finding at {0} sessions.".format(
                      record.as_dict()["minimum_sessions"]))
    print("   account readings: {0} days  |  {1} closes: {2} days".format(
        len(account), BENCHMARK, len(bars)))
    return record


def main():
    forward_section()

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
    print("   Risk-adjusted (CONFIRMED; rf = 3-month bill, 2.30% mean 1996-2026):")
    print("   {0:<32}{1:>15}{2:>9}{3:>8}{4:>7}".format("", "Sharpe(excess)", "Sortino", "Calmar", "beta"))
    for row in (("30 yrs  candidate (parked)", "0.53", "0.75", "0.51", "0.205"),
                ("30 yrs  SPY price (TR ~0.42)", "0.40", "0.57", "0.15", "1"),
                ("decade  candidate (alone)", "0.67", "0.95", "0.68", ""),
                ("decade  SPY total return", "0.77", "1.07", "0.45", "1")):
        print("   {0:<32}{1:>15}{2:>9}{3:>8}{4:>7}".format(*row))
    print()
    print("   The candidate loses to SPY on return. Its advantage is DRAWDOWN: Calmar 3.4x")
    print("   and 1.7x, maxDD -11.2% vs -56.5% / -33.8%, beta 0.205. On Sharpe and Sortino")
    print("   it is a tie - ahead over thirty years, at or behind SPY total return over the")
    print("   decade. The rf=0 convention (0.87 vs 0.52) flattered it: 74% of its balance")
    print("   is cash earning the bill rate, which a zero-rf Sharpe counts as alpha.")
    print("   'Outperforms on a risk-adjusted basis' is true only if risk means drawdown.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
