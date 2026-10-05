---
title: "Trading Decision Guardrails"
authority: "NAVIGATION"
kind: "operational-research-guide"
generated: false
sources:
  - "docs/2026-10-03-day-trading-what-works.md"
  - "docs/2026-10-03-shorting-and-all-in-report.md"
  - "docs/2026-10-04-where-to-take-profit.md"
  - "docs/2026-10-04-bounce-take-profit-live.md"
  - "docs/2026-09-22-h0019-recognized-gains-news-audit.md"
  - "docs/phase4-clean-observation-protocol.md"
  - "docs/SPEC-0001-decision-boundary.md"
  - "src/event_aware_trader/autotrade.py"
  - "src/event_aware_trader/live_model.py"
  - "src/event_aware_trader/daily_report.py"
---

# Trading Decision Guardrails

> [!abstract] NAVIGATION — non-authoritative
> Organises and links. Asserts nothing beyond its cited sources and never overrides them.

> [!warning] Research guide, not a trading rule
> This page records what the evidence supports and what it does not. It does
> not authorize a strategy, risk, or broker change. [[Production Truth]],
> [[SPEC-0001]], the experiment ledger, and the clean-observation protocol
> remain authoritative.

*Snapshot: 2026-10-04, local working tree. Verify current source, configuration,
broker state, and ledgers before relying on any snapshot below.*

## No score is currently a verified win probability

`live_model_ranking` can reorder candidates that already passed the hand-built
entry rules. `live_model_floor` defaults to zero, so it is not a meaningful
probability threshold. The model's score has not been established here as a
calibrated probability that a specific trade will win after costs. AUC measures
ranking discrimination; it does not establish calibration, positive expectancy,
or a reason to increase size. The event now logged beside model scores makes
this limitation explicit.

Do not call an AUC, rank score, rule score, or win rate “confidence” unless a
pre-registered, strictly forward evaluation establishes calibration and
positive net expectancy for the same population, horizon, and execution model.
Even a calibrated win probability does not by itself determine position size:
payoff size, costs, drawdown, correlation, and uncertainty also matter.

## Recognized and unrealized gains

- Closed trades contribute realized trade P&L. Open positions show unrealized
  P&L; it can change before an exit fills and is not sale proceeds.
- The recognized-gains accounting audit found that backtest sale proceeds
  were recorded before same-session new-entry cash checks. That closed the
  accounting question for that audited path; it did not establish that the
  exit rules realize enough profit.
- `daily_report` now exposes the subtotal of open positions with a known mark,
  the count missing a mark, and whether the subtotal is complete. Do not
  interpret an incomplete subtotal as total unrealized P&L.

## Exits and confidence-dependent levels

The local configuration uses a broker-resident protective stop and a
broker-resident take-profit OCO when accepted. The take-profit mode is the
RSI-60 bounce price; the daily loop also applies rule exits. These mechanics
make exit levels visible and persistent, but the historical bounce-price
comparison is contaminated and did not clear its trade-level significance
threshold. The portfolio diagnostic is not clean out-of-sample proof. Broker
order acceptance and fills require broker-side verification; source code and
paper tests cannot establish that a particular live account has both legs
working.

Exit levels must not be widened or tightened from a purported confidence
score until the score is calibrated and the proposed level-sizing policy is
evaluated under a preregistered, clean holdout. A higher win rate alone is not
an improvement if expected net return falls or tail loss rises. Keep stops and
targets tied to the approved rule and risk limits while that evidence is
missing.

## Shorting decision

Do not enable a short sleeve on this evidence. The local H-0027–H-0029 tests
reported lower combined returns and risk-adjusted results for the tested short
rules; the live execution path is long-oriented and has additional borrow,
gap, dividend, and unlimited-loss concerns. These tests do not prove that all
short strategies are impossible. They do mean there is no evidence-based case
to make shorting a production strategy now.

## Required evidence before promoting a new strategy

1. Read [[Do Not Re-Research]], [[Research Gaps]], the experiment ledger, and
   the frozen strategy.
2. Register the hypothesis before measuring outcomes; name a verified,
   hashed dataset, population, benchmark basis, costs, and all prior trials.
3. Keep the clean holdout untouched. Do not tune a rule or model on its
   results; use the phase checkpoints for descriptive evaluation only.
4. Compare account-level total returns with SPY total returns over identical
   dates. Include cash yield, realistic spreads/slippage, dividends, exposure,
   drawdown, leverage, and year-by-year performance.
5. Confirm actual broker orders, fills, fees, and marks independently. Paper
   fills do not verify market impact, latency, or limit-order queue position.

## Operational security

The October 2026 local reports state that an Alpaca credential was exposed and
had not been rotated, and that the broker OCO change was not live-API verified.
Treat the credential as compromised until the owner confirms it was revoked
and replaced. Never include credentials in notes, logs, or research outputs.
Do not represent an OCO as broker-protected until the account's open orders
show an active protective stop and the intended target.

## Source notes

- [Day-trading research](../../docs/2026-10-03-day-trading-what-works.md) —
  tested day-trading approaches and SPY hurdle.
- [Short and all-in tests](../../docs/2026-10-03-shorting-and-all-in-report.md).
- [Take-profit study](../../docs/2026-10-04-where-to-take-profit.md) and
  [implementation status](../../docs/2026-10-04-bounce-take-profit-live.md).
- [Clean observation protocol](../../docs/phase4-clean-observation-protocol.md)
  — holdout boundaries and checkpoints.
