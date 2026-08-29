# Event-Aware Market Research Bot

This is a **paper-trading research tool**, not a profit machine and not a live-trading system. It turns a small, explicit set of real-world-event hypotheses into transparent market candidates, then applies conservative liquidity, cost, and risk gates before it will label anything `PAPER_LONG`.

It intentionally does **not** connect to a brokerage or submit real orders. The reference supplied with this project makes a strong case that retail intraday direction prediction is especially unreliable, so this project is designed to measure a hypothesis honestly before any money is at risk.

## What it does

- Reads daily OHLCV data from CSV or optionally downloads it with Yahoo Finance through `yfinance`.
- Converts RSS headlines or a reviewed event file into auditable, rule-based macro/event assessments.
- Maps event scenarios to a deliberately small, liquid ETF universe (`SPY`, `QQQ`, `XLK`, `XLE`, `XLF`, `TLT`, `GLD`).
- Requires trend, liquidity, volatility, transaction-cost, and event-alignment checks before generating a **long-only paper-trade candidate**.
- Sizes the candidate at a default **0.5% account risk**, with a **1.5% daily-loss guard** and no leverage, options, shorts, microcaps, or averaging down.
- Backtests without look-ahead: a signal formed after a daily close enters no earlier than the next daily open, with adverse same-bar stop/target handling and estimated spread/slippage.
- Separates an untouched final test segment from the earlier segment; it does not optimize parameters for the test period.
- Monitors opt-in, pinned social accounts (Bluesky, X, or official RSS) and writes verified-source **review alerts**. A social post can never place a trade or set a trade direction.
- Learns from reviewed paper outcomes only, then scores a human-defined scenario against a chronological out-of-sample test set. It marks small or poorly calibrated models `UNPROVEN`.

The signal score is an evidence gate, **not a probability of profit**. A rejected trade is a valid outcome.

## Install

Use Python 3.9 or newer. Create an isolated environment, then install the package in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Run the dependency-free unit tests:

```bash
python -m unittest discover -s tests -v
```

## Quick start

1. Download daily data for a liquid ETF. This only retrieves market data; it never contacts a broker.

```bash
event-aware-trader fetch --symbol SPY --period 2y --out data/SPY.csv
```

2. Copy and review the supplied event template. Do not treat an automatic headline label as fact; set the category and stance only after checking the primary source.

```bash
cp examples/events.example.json data/events.json
event-aware-trader analyze --symbol SPY --prices data/SPY.csv --events data/events.json
```

3. Screen the default liquid ETF universe and record only candidates that clear every gate.

```bash
event-aware-trader screen --events data/events.json --period 2y --out-dir data
```

4. Measure the exact rule on historical data before acting on it. The result is a diagnostic, not proof of edge.

```bash
event-aware-trader backtest --symbol SPY --prices data/SPY.csv --events data/events.json
```

5. To turn a public RSS feed into a *review queue* of event labels:

```bash
event-aware-trader rss --feed 'https://example.com/feed.xml' --out data/review-events.json
```

Review that file, correct the category/stance/confidence, then use it as the `--events` input. The RSS classifier is transparent keyword logic by design; it is not a claim of understanding or truth.

## Event-file format

`examples/events.example.json` contains a complete example. Each event can specify:

- `title` — concise description of the fact or release.
- `category` — `inflation`, `central_bank`, `energy`, `growth`, `geopolitics`, `earnings`, or `other`.
- `stance` — `hawkish`, `dovish`, `risk_on`, `risk_off`, or `neutral`.
- `confidence` — your confidence in the *classification* from 0 to 1, not a forecast probability.
- `published_at` — when the information became public; historical backtests ignore events not yet public.
- `scheduled_at` — optional known release time. New candidates are blocked in the configured blackout window around this time.
- `source` and `url` — provenance, preferably a primary source.

## Verified social monitoring

Social posts are useful for awareness but not trustworthy enough to drive an order by themselves. The `social` command makes a fast, append-only *review queue* from a small allow-list of sources you have independently verified.

```bash
cp examples/social-sources.example.json data/social-sources.json
cp examples/entities.example.json data/entities.json
# Verify and enable an account, then:
event-aware-trader social --sources data/social-sources.json --entities data/entities.json
```

The system rejects an enabled source unless it is marked official and pinned to a platform-specific immutable identity:

- **Bluesky:** actor plus immutable DID (and optionally the exact handle).
- **X:** an X developer bearer token plus a pinned immutable author ID; set `X_BEARER_TOKEN` in your shell, never in a file.
- **RSS:** a feed URL pinned to the independently verified official domain.

An exact account match, a fresh timestamp, and a reviewed entity alias can produce `REVIEW_REQUIRED`. That still means only: *open the post, read the context and primary evidence, choose a scenario manually, and use paper trading if appropriate.* It does not infer whether a Dell mention is positive or negative, whether it is already priced in, or whether Dell stock should be bought or sold.

For a continuous monitor, run this in a terminal you control; `--iterations 0` is deliberately explicit:

```bash
event-aware-trader social \
  --sources data/social-sources.json \
  --entities data/entities.json \
  --iterations 0
```

## Why it cannot "act faster than humans"

Professional firms use direct market data, low-latency infrastructure, specialised execution systems, and compliance controls. Public social APIs add delay and can be changed, rate limited, impersonated, or wrong. This project improves *structured monitoring and evidence capture*; it does not claim a speed edge or promise a profit.

## Training the research model

The bot can improve only from a labelled record of decisions and their completed **paper** outcomes. It does not learn from raw social text, headline hype, or live account balances.

For each reviewed scenario, write one JSON line containing the source platform, trust score, post age, entity count, your manually chosen `up` or `down` scenario, claim type, fixed horizon, friction estimate, and observed forward return. See `examples/training-examples.example.jsonl` for the exact schema.

The example file has only three illustrative rows and is intentionally too small to train; it demonstrates the format, not an edge.

```bash
event-aware-trader train \
  --examples data/reviewed-paper-outcomes.jsonl \
  --model data/research-model.json
```

Training always holds out the newest 30% of examples. The report includes the out-of-sample Brier score, a base-rate comparison, and calibration bins. A model stays `UNPROVEN` until it has at least 200 examples, at least 50 untouched final-period examples, better-than-base Brier performance, and acceptable calibration. Even a `RESEARCH_ONLY_CANDIDATE` never enables automatic trading.

To score a scenario that *you* have reviewed and given a direction:

```bash
event-aware-trader forecast \
  --model data/research-model.json \
  --scenario examples/forecast-scenario.example.json
```

The result is `HOLD_FOR_HUMAN_REVIEW`, not a buy or sell command. This distinction is intentional: no training set can eliminate market uncertainty, false information, delayed reactions, or trading costs.

## Default safeguards

The safeguards are intentional implementation choices derived from the supplied reference:

- Long-only, liquid ETFs only; no leveraged ETFs, shorts, options, crypto, futures, or low-float stocks.
- Default `0.5%` maximum risk per candidate, `1.5%` maximum daily loss, and `6%` weekly loss guard.
- Fixed stop and target are calculated before position size. A candidate is rejected if its expected move does not exceed twice the modeled round-trip cost.
- No entry around a scheduled macro event; event headlines are a scenario input, not a reason to gamble on a release.
- Only one position per correlation bucket at a time (broad equity, technology, energy, financials, duration, or gold).
- Backtests include a configurable 6 basis-point one-way spread/slippage estimate and conservative stop handling when a daily bar reaches both stop and target.

## Important limits

- Free/delayed data, keyword classification, daily bars, and backtests cannot establish a tradeable intraday edge.
- Backtests do not include all real costs, market impact, delistings, halts, data errors, taxes, or changing regimes. Treat results as an attempt to disprove a rule.
- No strategy can make “no mistakes” or guarantee profits. Do not risk money that would affect your life; paper trade and journal a large sample first.
- If this ever progresses beyond research, add independent audit logs, broker-specific compliance review, live market-data validation, kill switches, and human approval. Do not add automatic live execution by default.
- Never automatically trade from a political figure's, executive's, influencer's, or anonymous account post. Even a real post can be ambiguous, already priced in, deleted, altered, or misinterpreted.

## Project layout

```text
src/event_aware_trader/  core package
examples/                reviewed-event template
tests/                   unit tests for safety-critical calculations
data/                    local downloaded data and journals (gitignored)
```
