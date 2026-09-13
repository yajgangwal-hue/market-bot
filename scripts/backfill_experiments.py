"""Back-fill the experiment registry with everything tried 2026-09-08..13.

Every entry below was evaluated on data that is now contaminated for the
production candidate. Recording them is not bookkeeping: `related_before`
is what the deflated-Sharpe correction needs, and the count per family is
what tells the next person that "exits" has been tried fifteen ways.

Failed experiments are recorded with the same care as the one that shipped.
Run once; refuses to run on a non-empty registry.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from event_aware_trader.research import REGISTRY, load_registry, record_experiment

D, T, E, C = "decade", "thirty_year", "etf_subset", "crypto"

ENTRIES = [
    # when, family, hypothesis, config, data, result, decision, evidence, reason
    ("2026-09-08", "sizing", "Two names per correlation bucket raises deployed capital without doubling risk",
     {"max_per_bucket": 2}, [D], "worse drawdown, no return gain", "rejected", "contradictory",
     "the bucket exists because two names in it are one trade twice"),
    ("2026-09-08", "baseline", "The shipped rule survives two real bear markets",
     {}, [T], "CAGR 4.6%, maxDD -16.3%; 2008 -8.7%", "measured", "strong",
     "established the thirty-year window as the deciding test"),
    ("2026-09-08", "crypto", "Some crypto trading family (MR, trend, breakout, xs-momentum) has an edge in the account",
     {"asset_class": "crypto"}, [C], "every family lost; the rule cannot fire on crypto (0 trades)", "rejected", "strong",
     "structural: risk-budget sizing over a 4-13% daily range gives a position too small to matter"),
    ("2026-09-09", "filters", "Removing the 200-day trend filter raises position count and return",
     {"trend_ma_days": 0}, [D, T], "decade +2 CAGR pts; thirty-year maxDD -16.3% -> -37.9%, 2008 -25.8%", "reverted", "contradictory",
     "shipped, then reverted by the owner after one red day; the drawdown is the filter's purpose"),
    ("2026-09-09", "measurement", "Most of the return is the close-to-open gap",
     {}, [D], "73.6% of return is overnight; universe +0.0548%/night vs +0.0307% intraday", "measured", "strong",
     "the finding every later entry/exit decision rests on"),
    ("2026-09-09", "retune", "With the filter off, a different RSI/stop/exit setting beats the old one",
     {"variants": 26}, [D], "26 variants, none cleared both halves", "rejected", "none",
     "post-hoc retune after a config change"),
    ("2026-09-09", "intraday", "Trading the intraday swings inside a held position adds return",
     {"intraday_swings": True}, [D], "192,000 trades, zero gross edge", "rejected", "strong", "no intraday edge exists here"),
    ("2026-09-10", "entries", "Acting on the signal sooner within the day recovers lost return",
     {"entry_latency": "measured"}, [D], "3,785 signal days: latency costs nothing", "measured", "strong",
     "the loss was not latency, it was the next-day open (see entries 09-11)"),
    ("2026-09-10", "filters", "Volatility targeting and/or a market regime filter improve risk-adjusted return",
     {"vol_target": True, "regime_filter": True}, [D, T], "both worse or flat", "rejected", "contradictory", "risk reduction without return; drawdown not improved"),
    ("2026-09-10", "overnight", "Names with persistent overnight gaps can be selected and held one night for a profit",
     {"overnight_rank": "top 10%..1%"}, [D], "top 10% clears costs both halves as a statistic", "measured", "weak",
     "not built; survivorship and capacity flagged. Priced as an account 09-11."),
    ("2026-09-10", "shorting", "A short book on the rule's mirror signal adds return",
     {"short_book": True}, [D], "per-trade edge dies in the account", "rejected", "contradictory", "sizing and borrow kill it"),
    ("2026-09-10", "shorting", "Shorting the bot's own long signals is profitable (inverse)",
     {"invert": True}, [D], "25,643 signals, no gradient", "rejected", "none", "no gradient either direction"),
    ("2026-09-10", "shorting", "Shorting after a violent open captures continuation",
     {"volatile_open_short": True}, [D], "154,131 sessions: shorting negative in every bucket; long-after-up-open positive but decaying 9x", "rejected", "contradictory",
     "the long half priced as an account 09-11 and rejected"),
    ("2026-09-10", "capital", "Parking idle cash in a T-bill ETF adds return at no drawdown cost",
     {"cash_parking_symbol": "SGOV"}, [D, T], "+1.49 CAGR pts, drawdown unchanged", "accepted", "strong", "interest cannot lose money; shipped"),
    ("2026-09-10", "crypto", "A 5% BTC allocation held above its 100-day average diversifies the equity book",
     {"sleeve_fraction": 0.05, "trend_days": 100}, [C, D], "corr +0.035; CAGR 7.60 -> 9.13, maxDD -14.1 -> -13.5", "accepted", "weak",
     "return is 0.05 x BTC's historical return, not an edge; drawdown improvement is real. Shipped 24/7 on 09-12."),
    ("2026-09-11", "entries", "Filling at the signal bar's own close instead of the next open captures the overnight gap",
     {"entry_fill": "signal_close"}, [D, T], "decade +1.32 (cost-matched at 3/6/9/12bps all positive); thirty-year +1.08, maxDD -16.3 -> -14.2, both halves", "accepted", "strong",
     "mechanism is causal (73.6% of return is the gap the bot was sitting out). SHIPPED as the 15:45 window."),
    ("2026-09-11", "entries", "A 30-minute window gives two chances at the fill",
     {"entry_window_minutes": 30}, ["decade"], "15:30 fill -0.0295% vs 15:45 +0.0257% on 1,417 oversold sessions", "reverted", "strong",
     "entries fire on the first cycle so 30 made 15:30 the default; corrected to 20"),
    ("2026-09-11", "exits", "Selling a position that was losing last night and opens green captures the gap",
     {"rescue_exit": True}, [D], "win rate 53 -> 67%, CAGR 7.83 -> 6.41", "rejected", "contradictory", "truncates the top-50 trades that carry 86% of profit"),
    ("2026-09-11", "exits", "Shorter holding periods (day trading) earn more",
     {"max_holding_bars": [1, 3, 20]}, [D], "1 day -39.3%, 3 days +5.2%, 20 days +123.1%", "rejected", "strong", "monotone in holding period; the edge is overnight"),
    ("2026-09-11", "filters", "With the better entry, the trend filter can come off",
     {"trend_ma_days": 0, "entry_fill": "signal_close"}, [D, T], "thirty-year +1.35 CAGR for +19.2 pts drawdown, 2008 -22.6%", "rejected", "contradictory", "same trade as before; filter stays"),
    ("2026-09-11", "sizing", "A different per-name cap beats 20%",
     {"max_notional_fraction": [0.10, 0.15, 0.20, 0.25]}, [D, T], "clean peak at 20% on both windows", "rejected", "strong", "smaller positions take more trades and earn less"),
    ("2026-09-11", "exits", "A different stop width beats 2.5 ATR",
     {"stop_atr_multiple": [2.0, 2.5, 3.0, 3.5, 4.0]}, [D, T], "clean peak at 2.5; wider raises win rate and loses a third", "rejected", "strong", "fewer losers is not more money"),
    ("2026-09-11", "exits", "A higher RSI exit keeps more of the recovery",
     {"rsi_exit": [55, 60, 65, 70]}, [D, T], "decade +1.12/+1.43 pts; thirty-year +0.17/+0.11, first half worse, drawdown worse", "rejected", "contradictory",
     "decade result reversed; at 70 only 6% of trades reach the exit"),
    ("2026-09-11", "exits", "A longer holding cap captures more",
     {"max_holding_bars": [20, 25, 30, 40, 60]}, [D], "every longer cap worse", "rejected", "strong", ""),
    ("2026-09-11", "ranking", "Ranking candidates by overnight persistence / conviction / oversold depth beats arbitrary order",
     {"candidate_rank": ["alphabetical", "oversold", "overnight", "conviction"]}, [D, T], "0.58-pt spread, ordering flips between windows", "rejected", "none",
     "noise; also found the simulator had been allocating alphabetically, and a cache bug that moved a 30-yr result by 0.5 pts"),
    ("2026-09-11", "shorting", "Long the violent up-opens / short the down-opens as an account",
     {"volatility_direction": True}, [D, T], "-52% to -64% CAGR, -100% drawdown, all variants", "rejected", "strong", "signal IS the open; unfillable"),
    ("2026-09-11", "overnight", "Buy the most persistent overnight gappers at the close, sell at the open",
     {"overnight_book": "top 3..25"}, [D, T, E], "23.6%/yr on the survivor set, every control passed; -1.5%/yr on ETFs", "rejected", "artifact",
     "survivorship: the effect vanishes on a universe that cannot delist"),
    ("2026-09-11", "capital", "Idle cash in SPY instead of T-bills",
     {"cash_parking_symbol": "SPY", "fraction": [0.25, 0.5, 0.75, 1.0]}, [D, T], "+1.17 CAGR for maxDD -11.7 -> -39.3", "rejected", "contradictory", "risk-adjusted 3x worse"),
    ("2026-09-12", "model", "The live model's veto (fit before 2015) removes losers after 2015",
     {"live_model_floor": [0.05, 0.08, 0.12, 0.15]}, [T], "veto loses money monotonically, -0.45 to -2.52 pts; AUC 0.5501 full-fit vs 0.5056 walk-forward", "rejected", "contradictory",
     "AUC was a period artifact; guard written beside live_model_floor"),
    ("2026-09-12", "measurement", "The simulator's assumptions match what the bot runs",
     {"whole_shares": True, "max_entries_per_day": 3, "mark_to_market_guard": True}, [D, T], "net +0.02 over 30 yrs; guard alone -0.26; stop fills at stop cost -0.23; dividends unmodelled +0.5-0.8", "measured", "strong",
     "produced the production-candidate definition and realistic_stop_fills"),
    ("2026-09-12", "measurement", "The main rule's edge survives a survivorship-free universe",
     {"universe": "46 ETFs"}, [D, T, E], "decade 9.14 -> 3.82; thirty-year 5.66 -> 2.24, positive both halves", "measured", "strong",
     "edge is real; size is inflated by survivorship; range is the honest claim"),
    ("2026-09-12", "crypto", "A larger BTC allocation or an ETH/split sleeve improves the combined account",
     {"sleeve_fraction": [0.05, 0.10, 0.15, 0.20], "assets": ["BTC", "ETH", "50/50"]}, [C, D], "return rises, second half falls with every step; drawdown benefit only at 5%", "rejected", "contradictory", "first-half bet"),
    ("2026-09-13", "crypto", "A different trend window on the sleeve beats 100 days",
     {"trend_days": [20, 50, 100, 150, 200]}, [C], "sawtooth 60.9/73.9/64.0/76.7/60.7", "rejected", "none", "noise"),
    ("2026-09-13", "crypto", "The trend allocation is profitable on meme coins at their real spread",
     {"assets": ["DOGE", "SHIB", "PEPE", "TRUMP"], "spread_bps": [32, 38, 29, 32]}, [C], "all lose or fail both halves; DOGE 2.7%/yr at -95% DD vs 5.4% hold", "rejected", "strong", "tradeable, unallocated"),
    ("2026-09-13", "crypto", "A trailing stop on the BTC sleeve exits crashes sooner",
     {"trail_atr": [2, 3, 4, 6]}, [C], "74.7/61.0/63.0/65.2 vs 64.0 plain; one good cell", "rejected", "none", "sawtooth"),
    ("2026-09-13", "exits", "Trailing stops, partial profits, momentum and regime exits beat the fixed rule on the honest emulator",
     {"variants": 11}, [D, T], "partial/momentum raise win rate and lose money; trail 1.0R/3.0ATR +0.06 and regime +0.03 over 30 yrs", "rejected", "weak",
     "two clear the gate by rounding; complexity in the money path not justified for $60/yr"),
]

# How many distinct settings each row stands for, in ENTRIES order. A sweep of
# five stops is one hypothesis and five configurations; the deflated Sharpe
# pays for configurations, not hypotheses.
CONFIGURATIONS = [
    1, 1, 4, 1, 1, 26, 1, 1, 2, 4,      # 09-08 .. 09-10 overnight rank
    1, 1, 1, 1, 1, 1, 2, 1, 3, 1,       # shorting x3, SGOV, BTC 5%, entries, window, rescue, holding, filter
    4, 5, 4, 5, 4, 4, 4, 4, 4, 4,       # caps, stops, RSI, holding, ranking, vol-direction, overnight book, SPY, floors, live constraints
    1, 12, 5, 4, 4, 11,                 # ETF universe, sleeve, trend window, meme, trail, exit variants
]
assert len(CONFIGURATIONS) == len(ENTRIES), (len(CONFIGURATIONS), len(ENTRIES))

# The Sharpes of every configuration in a sweep, where they were written down.
# Only the 09-13 exit sweep recorded one per configuration (decade, honest
# fills; the baseline is the first value). This spread - not an assumed one -
# is what the deflation uses from here on.
TRIAL_SHARPES = {
    35: [0.88, 0.62, 0.82, 0.91, 0.80, 0.85, 0.80, 0.88, 0.89, 0.90, 0.83],
}


def main():
    if load_registry(REGISTRY):
        raise SystemExit("registry is not empty; refusing to back-fill twice")
    for i, (when, family, hypothesis, config, data, result, decision, evidence,
            reason) in enumerate(ENTRIES):
        record_experiment(family=family, hypothesis=hypothesis, config=config,
                          data_periods=data, result=result, decision=decision,
                          reason=reason, evidence=evidence, contaminated=data,
                          configurations=CONFIGURATIONS[i],
                          trial_sharpes=TRIAL_SHARPES.get(i), when=when)
    rows = load_registry(REGISTRY)
    print("recorded {0} experiments ({1} configurations) to {2}".format(
        len(rows), sum(r["configurations"] for r in rows), REGISTRY))
    by = {}
    for r in rows:
        by[r["family"]] = by.get(r["family"], 0) + 1
    for family, n in sorted(by.items(), key=lambda kv: -kv[1]):
        print("   {0:<12} {1}".format(family, n))


if __name__ == "__main__":
    main()
