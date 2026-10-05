"""Generate a TradingView indicator showing the bot's REAL live exit levels.

WHY THIS IS GENERATED RATHER THAN WRITTEN ONCE

Pine Script cannot fetch external data. There is no way for a TradingView
indicator to ask this machine what the bot currently holds, so the levels have
to be baked into the script and the script regenerated whenever they change.
`session-run.ps1` calls this every cycle, so the file on disk is always
current; TradingView shows the new values once the script is re-pasted or the
saved indicator is updated.

WHAT IT DRAWS

  RED ZONE         entry down to the stop: what the position can lose before
                   the broker's resting GTC stop closes it.
  GREEN ZONE       entry up to the take profit: what it makes if the take
                   profit is reached first.
  stop loss        a real price, resting at the broker as a GTC stop order.
  take profit      a real price since EXP-0055 (sessions from 2026-09-29).
                   Since EXP-0056 it also RESTS AT THE BROKER, as the limit
                   half of a one-cancels-other order whose other half is the
                   stop, so a broker panel connected to the account shows
                   both; the bot still checks it every cycle as a backstop.
                   If the broker refuses the OCO the bot falls back to a plain
                   stop for that session, and the level is then only here.
  entry            the broker's average fill.
  RSI exit         the rule closes when DAILY RSI(14) >= 60. Pine computes it
                   itself, so it is drawn live rather than baked in.
  holding cap      20 sessions, counted exactly the way the bot counts them:
                   daily bars dated after the entry day it recorded.
  a table          the levels, the money at stake, and what trades with these
                   exits did in the 2016-2026 simulation - the conservative
                   figure first (docs/2026-09-28-expected-returns.md).

WHERE THE TAKE PROFIT COMES FROM

The level the bot itself uses: the one remembered in its state file, or - for
a position the bot has not yet looked at under EXP-0055 - the level
`autotrade._take_profit_for` will set on its first look, computed by that
same function on a COPY of the state, so this script never writes it.

WHERE THE ENTRY PRICE COMES FROM

The broker, when run normally: the average fill, which is also what the bot
computes the take profit from. Each such run saves what it read to
data/tradingview-levels.json, and --offline redraws from that snapshot
without calling anything. Local state alone cannot supply an entry price: it
records stops, not fills.
"""

import argparse
import copy
import json
from dataclasses import MISSING, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "tradingview" / "live-levels.pine"
DEFAULT_STATE = REPO / "data" / "autotrade-state.json"
DEFAULT_SNAPSHOT = REPO / "data" / "tradingview-levels.json"
DEFAULT_EXPECTED = REPO / "docs" / "phase5" / "expected-returns-2026-09-28.json"

HEADER = '''// ============================================================
// Bot live levels - GENERATED, do not edit by hand
// Regenerated {generated} UTC by scripts/tradingview_levels.py
// Entry prices: {source}
// ------------------------------------------------------------
// Pine Editor -> New indicator -> select all -> paste -> Save
// -> Add to chart. Use a DAILY (1D) chart: the rule is daily.
// Re-paste after the bot opens or closes a position; Pine
// cannot read this machine, so the numbers are baked in.
//
// Positions represented: {count}
//
// EXITS. The stop, the RSI exit and the time limit come first;
// the take profit is checked after them.
//  - stop: a GTC stop order resting at the broker
//  - RSI: daily RSI({rsi_len}) >= {rsi_exit:.0f}
//  - time: {hold} sessions held, counted the way the bot counts
//  - take profit: {take_note}
{take_where}//
// EXPECTED RETURNS are from a SIMULATION of 2016-2026 on data
// this strategy was built on, with today's surviving stocks.
// Both make it look better than it will be. The conservative
// line charges the take-profit sale the same execution cost as
// every other rule exit. docs/2026-09-28-expected-returns.md
// ============================================================
//@version=6
indicator("Bot Live Levels", overlay=true, max_bars_back=100)

rsiExit  = input.float({rsi_exit}, "RSI exit level", group="Rule")
rsiLen   = input.int({rsi_len},  "RSI length",      group="Rule")
holdBars = input.int({hold}, "Holding cap (sessions)", group="Rule")
showZone = input.bool(true, "Shade the RSI exit zone", group="Display")
showExp  = input.bool(true, "Show expected returns", group="Display")

LEVELS_STAMP  = "{generated}"
LEVELS_SOURCE = "{source_short}"

// Per trade, from the simulation, for the exits in force.
EXP_KNOWN  = {exp_known}
EXP_TP     = {exp_tp}
EXP_STOP   = {exp_stop}
EXP_OTHER  = {exp_other}
EXP_R_CONS = {exp_r_cons}
EXP_R_SIM  = {exp_r_sim}
// The rule-exit execution haircut, charged to the take-profit sale in
// the conservative line (a fraction of the sale price).
HAIRCUT    = {haircut}
// The account, a year (percent).
ACCT_CONS  = {acct_cons}
ACCT_SIM   = {acct_sim}
SPY_TR     = {spy_tr}

sym = syminfo.ticker

entryPrice = 0.0
stopPrice  = 0.0
takePrice  = 0.0
shares     = 0.0
entryDay   = 0
'''

BODY = '''
holding = stopPrice > 0 and entryPrice > stopPrice

pctFrom(level, base) =>
    (level - base) / base * 100

fmtPct(x) =>
    (x >= 0 ? "+" : "-") + str.tostring(math.abs(x), "0.0") + "%"

fmtUsd(x) =>
    (x >= 0 ? "+$" : "-$") + str.tostring(math.abs(x), "#,##0")

fmtR(x) =>
    (x >= 0 ? "+" : "-") + str.tostring(math.abs(x), "0.00") + "R"

// The rule is daily, so its RSI is daily whatever the chart shows.
dailyRsi = request.security(syminfo.tickerid, "D", ta.rsi(close, rsiLen))

// The bot's own count: daily bars dated after the entry day it recorded.
dateKey = year(time) * 10000 + month(time) * 100 + dayofmonth(time)
afterEntry = holding and entryDay > 0 and dateKey > entryDay

// ---- zones, lines and labels ------------------------------------------------
var box riskBox = na
var box gainBox = na
var line stopLine = na
var line entryLine = na
var line takeLine = na
var label stopLabel = na
var label entryLabel = na
var label takeLabel = na

if barstate.islast
    if not na(riskBox)
        box.delete(riskBox)
    if not na(gainBox)
        box.delete(gainBox)
    if not na(stopLine)
        line.delete(stopLine)
    if not na(entryLine)
        line.delete(entryLine)
    if not na(takeLine)
        line.delete(takeLine)
    if not na(stopLabel)
        label.delete(stopLabel)
    if not na(entryLabel)
        label.delete(entryLabel)
    if not na(takeLabel)
        label.delete(takeLabel)
    if holding
        left = math.max(0, bar_index - 120)
        right = bar_index + 20
        riskBox := box.new(left, entryPrice, right, stopPrice,
             border_color=color.new(color.red, 40), bgcolor=color.new(color.red, 88))
        stopLine := line.new(left, stopPrice, right, stopPrice,
             color=color.red, width=2)
        stopLabel := label.new(right, stopPrice,
             "STOP  " + str.tostring(stopPrice, format.mintick) + "  " + fmtPct(pctFrom(stopPrice, entryPrice)),
             style=label.style_label_left, color=color.new(color.red, 85),
             textcolor=color.red, size=size.small)
        entryLine := line.new(left, entryPrice, right, entryPrice,
             color=color.new(color.gray, 30), width=1, style=line.style_dashed)
        entryLabel := label.new(right, entryPrice,
             "entry " + str.tostring(entryPrice, format.mintick),
             style=label.style_label_left, color=color.new(color.gray, 90),
             textcolor=color.gray, size=size.small)
        if takePrice > entryPrice
            gainBox := box.new(left, takePrice, right, entryPrice,
                 border_color=color.new(color.green, 40), bgcolor=color.new(color.green, 88))
            takeLine := line.new(left, takePrice, right, takePrice,
                 color=color.green, width=2)
            takeLabel := label.new(right, takePrice,
                 "TAKE PROFIT  " + str.tostring(takePrice, format.mintick) + "  " + fmtPct(pctFrom(takePrice, entryPrice)),
                 style=label.style_label_left, color=color.new(color.green, 85),
                 textcolor=color.green, size=size.small)

// ---- the RSI exit: a condition, so it is shaded rather than drawn -----------
inExitZone = afterEntry and timeframe.isdaily and dailyRsi >= rsiExit
bgcolor(showZone and inExitZone ? color.new(color.green, 88) : na, title="RSI exit zone")
plotshape(inExitZone and dailyRsi[1] < rsiExit, title="RSI exit triggers",
     style=shape.triangledown, location=location.abovebar, color=color.green,
     size=size.tiny, text="exit")

// ---- the holding cap --------------------------------------------------------
held = 0
if barstate.islast and holding and entryDay > 0 and timeframe.isdaily
    for i = 0 to math.min(bar_index, 60)
        if dateKey[i] > entryDay
            held += 1

var line capLine = na
if barstate.islast
    if not na(capLine)
        line.delete(capLine)
    if holding and entryDay > 0 and timeframe.isdaily
        capX = bar_index + math.max(holdBars - held, 0)
        capLine := line.new(capX, low, capX, high, color=color.new(color.orange, 20),
             width=1, style=line.style_dotted, extend=extend.both)

// ---- the table --------------------------------------------------------------
setRow(tbl, row, leftText, rightText, rightColor) =>
    table.cell(tbl, 0, row, leftText, text_color=color.gray, text_size=size.small)
    table.cell(tbl, 1, row, rightText, text_color=rightColor, text_size=size.small)

var table panel = table.new(position.top_right, 2, 18, border_width=1)
if barstate.islast
    fg = chart.fg_color
    table.cell(panel, 0, 0, "Bot", text_color=color.white,
         bgcolor=color.new(color.blue, 40), text_size=size.small)
    table.cell(panel, 1, 0, holding ? "HOLDING " + sym : "not held by the bot",
         text_color=color.white, bgcolor=color.new(color.blue, 40), text_size=size.small)
    riskUsd = holding ? (entryPrice - stopPrice) * shares : 0.0
    rewardUsd = holding and takePrice > entryPrice ? (takePrice - entryPrice) * shares : 0.0
    if holding
        setRow(panel, 1, "entry", str.tostring(entryPrice, format.mintick), fg)
        setRow(panel, 2, "stop", str.tostring(stopPrice, format.mintick) + "  " + fmtPct(pctFrom(stopPrice, entryPrice)), color.red)
        setRow(panel, 3, "take profit", takePrice > entryPrice ? str.tostring(takePrice, format.mintick) + "  " + fmtPct(pctFrom(takePrice, entryPrice)) : "none", color.green)
        setRow(panel, 4, "lose at stop / make at target", fmtUsd(-riskUsd) + " / " + (takePrice > entryPrice ? fmtUsd(rewardUsd) : "-"), fg)
        setRow(panel, 5, "open P&L now", fmtUsd((close - entryPrice) * shares) + "  " + fmtPct(pctFrom(close, entryPrice)), close >= entryPrice ? color.green : color.red)
        setRow(panel, 6, "daily RSI", str.tostring(dailyRsi, "0.0") + " / " + str.tostring(rsiExit, "0"), dailyRsi >= rsiExit ? color.green : fg)
        setRow(panel, 7, "sessions held", timeframe.isdaily ? str.tostring(held) + " of " + str.tostring(holdBars) : "open a 1D chart", fg)
    if showExp
        setRow(panel, 8, "PER TRADE (2016-26 sim)", "", fg)
        if EXP_KNOWN
            // As simulated: the average trade's R times this position's risk.
            // Conservative: the same, less the haircut on the take-profit sale
            // in dollars, weighted by how often the take profit is hit - so a
            // narrow stop, where the haircut is a larger share of R, pays more.
            simUsd = EXP_R_SIM * riskUsd
            consUsd = simUsd - EXP_TP * HAIRCUT * takePrice * shares
            consR = riskUsd > 0 ? consUsd / riskUsd : EXP_R_CONS
            setRow(panel, 9, "take profit hit first", str.tostring(EXP_TP * 100, "0") + "% of trades", color.green)
            setRow(panel, 10, "stop hit first", str.tostring(EXP_STOP * 100, "0") + "% of trades", color.red)
            setRow(panel, 11, "RSI or time exit", str.tostring(EXP_OTHER * 100, "0") + "% of trades", fg)
            setRow(panel, 12, "expected, conservative", holding ? fmtR(consR) + "  = " + fmtUsd(consUsd) : fmtR(EXP_R_CONS) + " average", consR >= 0 ? color.green : color.red)
            setRow(panel, 13, "expected, as simulated", holding ? fmtR(EXP_R_SIM) + "  = " + fmtUsd(simUsd) : fmtR(EXP_R_SIM) + " average", fg)
        else
            setRow(panel, 9, "these exit levels", "not measured", color.orange)
        setRow(panel, 14, "ACCOUNT, A YEAR", "", fg)
        setRow(panel, 15, "bot: conservative / sim", fmtPct(ACCT_CONS) + " / " + fmtPct(ACCT_SIM), fg)
        setRow(panel, 16, "SPY, same years", fmtPct(SPY_TR), fg)
    // FRESHNESS. The numbers were baked in when the file was generated. If this
    // date is not today's, re-paste: a stale paste shows real-looking levels
    // for a position that may no longer exist.
    setRow(panel, 17, "levels from", LEVELS_STAMP + " (" + LEVELS_SOURCE + ")", color.gray)
'''


# ---------------------------------------------------------------------------
# What the bot holds, with the levels it will act on
# ---------------------------------------------------------------------------

def live_adaptive_config():
    """The adaptive-exit procedure the scheduled bot runs, or None if off.

    Read from AutoTradeConfig's own default, which is what the scheduled
    `autotrade` command constructs, so switching adaptive exits off there
    removes the take profit here too.
    """
    from event_aware_trader.autotrade import AutoTradeConfig
    for f in fields(AutoTradeConfig):
        if f.name == "adaptive_exits":
            if f.default_factory is not MISSING:
                return f.default_factory()
            return None if f.default is MISSING else f.default
    return None


def live_multiples(state_file: Path) -> Tuple[Optional[float], Optional[float]]:
    """(take profit, stop) in ATRs, exactly as run_once reads them each cycle."""
    config = live_adaptive_config()
    if config is None:
        return None, None
    from event_aware_trader.adaptive_exits import current_levels, params_path
    return current_levels(config, params_path(state_file))


def live_take_profit_mode() -> str:
    """'bounce' (EXP-0057) or 'atr' (EXP-0055), as the scheduled bot runs it."""
    return getattr(live_adaptive_config(), "take_profit_mode", "atr")


def take_profit_for(remembered: Dict[str, object], entry: float,
                    take_atr: Optional[float], symbol: Optional[str] = None) -> Optional[float]:
    """The bot's own level, from the bot's own function, on a copy of state.

    EXP-0057: in bounce mode that is the session's bounce price, computed
    from the same local price file the bot reads, so a position entered this
    cycle is drawn at the level the next cycle will rest at the broker.
    """
    if take_atr is None:
        return None
    from event_aware_trader.mean_reversion import MeanReversionConfig
    if live_take_profit_mode() == "bounce" and symbol:
        from event_aware_trader.autotrade import _bounce_take_profit, daily_bars
        closes = [bar.close for bar in daily_bars(symbol)]
        return _bounce_take_profit(copy.deepcopy(remembered), closes, MeanReversionConfig())
    from event_aware_trader.autotrade import _take_profit_for
    return _take_profit_for(copy.deepcopy(remembered), entry, take_atr,
                            MeanReversionConfig().stop_atr_multiple)


def entry_day(opened_at: str) -> int:
    """The entry day the bot counts from, as YYYYMMDD; 0 when unreadable.

    The bot takes `_parse_stamp(opened_at_ts).date()` and counts daily bars
    dated after it (autotrade, the bars_held expression), so this is the
    date the stamp itself carries - not the session the order filled in.
    """
    if not opened_at:
        return 0
    try:
        when = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00"))
    except ValueError:
        return 0
    return when.year * 10000 + when.month * 100 + when.day


def load_state_stops(state_file: Path) -> Dict[str, Dict[str, object]]:
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8")).get("stops", {}) or {}
    except (OSError, ValueError):
        return {}


def broker_holdings() -> Dict[str, Tuple[float, float]]:
    """symbol -> (average fill, shares), from the broker."""
    from event_aware_trader.broker import AlpacaPaperBroker
    out = {}
    for position in AlpacaPaperBroker().positions():
        out[str(position["symbol"])] = (float(position["average_entry_price"]),
                                        float(position.get("quantity") or 0.0))
    return out


def snapshot_holdings(snapshot: Path) -> Tuple[Dict[str, Tuple[float, float]], str]:
    """What the last broker-mode run saw, and when."""
    if not snapshot.exists():
        return {}, ""
    try:
        data = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, ""
    out = {}
    for row in data.get("rows", []):
        try:
            out[str(row["symbol"])] = (float(row["entry"]), float(row.get("shares") or 0.0))
        except (KeyError, TypeError, ValueError):
            continue
    return out, str(data.get("generated") or "")


def positions_and_stops(state_file: Path, use_broker: bool,
                        snapshot: Path = DEFAULT_SNAPSHOT) -> List[Dict[str, object]]:
    """What the bot holds, the stop it recorded, and the take profit it uses.

    The broker is the authority on WHAT is held and at what average fill - a
    position closed by hand elsewhere must not appear on the chart - and local
    state is the authority on the stop and take-profit PRICES, because those
    are entry-time facts the broker does not report back. Offline, the last
    broker read stands in for the broker, and only positions the bot still
    remembers are drawn.
    """
    stops = load_state_stops(state_file)
    if use_broker:
        held = broker_holdings()
    else:
        held, _ = snapshot_holdings(snapshot)
        held = {s: v for s, v in held.items() if s in stops}
    take_atr, _ = live_multiples(state_file)

    rows = []
    for symbol in sorted(held):
        entry, shares = held[symbol]
        recorded = stops.get(symbol) or {}
        stop = recorded.get("current") or recorded.get("initial")
        if not stop or entry <= 0:
            continue
        rows.append({
            "symbol": symbol,
            "entry": entry,
            "shares": shares,
            "stop": float(stop),
            "take_profit": take_profit_for(recorded, entry, take_atr, symbol),
            "take_profit_atr": take_atr,
            "opened_at": recorded.get("opened_at_ts") or "",
        })
    return rows


def write_snapshot(rows: List[Dict[str, object]], path: Path, generated: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"generated": generated, "source": "broker",
            "rows": [{"symbol": r["symbol"], "entry": r["entry"], "shares": r["shares"]}
                     for r in rows]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Expected returns, only for the exit levels they were measured for
# ---------------------------------------------------------------------------

def load_expected(path: Path = DEFAULT_EXPECTED) -> Optional[Dict[str, object]]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def expected_for(record: Optional[Dict[str, object]], take_atr: Optional[float],
                 stop_atr: Optional[float]) -> Optional[Dict[str, float]]:
    """The per-trade figures, or None when they describe different exits.

    Measured for one pair of multiples. If the learner moves either one, the
    figures no longer describe what the bot does, and the chart must say
    "not measured" rather than show them.
    """
    if not record or take_atr is None or stop_atr is None:
        return None
    if live_take_profit_mode() != str(record.get("take_profit_mode", "atr")):
        return None                      # measured for a different take profit
    try:
        if (abs(float(record["take_profit_atr"]) - float(take_atr)) > 1e-9
                or abs(float(record["stop_atr"]) - float(stop_atr)) > 1e-9):
            return None
        chart = record["chart"]
        return {k: float(chart[k]) for k in (
            "take_profit_first", "stop_first", "other_exit",
            "mean_r_conservative", "mean_r_simulated",
            "account_cagr_conservative_pct", "account_cagr_simulated_pct",
            "spy_total_return_cagr_pct")}
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# The Pine file
# ---------------------------------------------------------------------------

def _pine_number(value: float, places: int = 4) -> str:
    return "{0:.{1}f}".format(float(value), places)


def production_haircut() -> float:
    from event_aware_trader.research import PRODUCTION_CANDIDATE
    return float(PRODUCTION_CANDIDATE["rule_exit_timing_haircut"])


TAKE_AT_BROKER = (
    "// The take profit RESTS AT THE BROKER: with the stop it forms\n"
    "// one OCO order (one-cancels-other), so a chart connected to\n"
    "// the account shows both, and it works with this PC off.\n"
    "// The bot also checks it every 15 minutes as a backstop.\n")
TAKE_IN_BOT = (
    "// The take profit is NOT an order at the broker. The bot\n"
    "// compares the broker's price with it every 15 minutes in\n"
    "// market hours and sells at market when it is reached, so a\n"
    "// broker panel shows the stop order but never this level.\n")


def pine_for(rows, rsi_exit, rsi_len, hold, expected=None, take_atr=None,
             generated=None, source="broker", haircut=None, take_at_broker=False):
    generated = generated or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    haircut = production_haircut() if haircut is None else float(haircut)
    if take_atr is None:
        take_note = "none - adaptive exits are switched off"
    elif live_take_profit_mode() == "bounce":
        take_note = ("the bounce price: the close that would put daily RSI(14) at 60, "
                     "from the closes through the last completed session (EXP-0057); "
                     "it moves once a day")
    else:
        take_note = "entry + {0:g} x the entry ATR (EXP-0055)".format(float(take_atr))
    known = expected is not None
    exp = expected or {}
    lines = [HEADER.format(
        generated=generated, source=source,
        source_short="broker" if source == "broker" else "snapshot",
        count=len(rows), rsi_exit=rsi_exit, rsi_len=rsi_len, hold=hold,
        take_note=take_note,
        take_where=(TAKE_AT_BROKER if (take_at_broker and take_atr is not None) else TAKE_IN_BOT),
        exp_known="true" if known else "false",
        exp_tp=_pine_number(exp.get("take_profit_first", 0.0)),
        exp_stop=_pine_number(exp.get("stop_first", 0.0)),
        exp_other=_pine_number(exp.get("other_exit", 0.0)),
        exp_r_cons=_pine_number(exp.get("mean_r_conservative", 0.0)),
        exp_r_sim=_pine_number(exp.get("mean_r_simulated", 0.0)),
        haircut=_pine_number(haircut, 5),
        acct_cons=_pine_number(exp.get("account_cagr_conservative_pct", 0.0), 2),
        acct_sim=_pine_number(exp.get("account_cagr_simulated_pct", 0.0), 2),
        spy_tr=_pine_number(exp.get("spy_total_return_cagr_pct", 0.0), 2))]
    if not rows:
        lines.append("// The bot holds nothing right now, so no levels are set.\n")
    for row in rows:
        # Pine has no dictionaries, so the held symbols become a chain of
        # comparisons against the charted ticker. TradingView spells a share
        # class "BRK.B" where this project says "BRK-B".
        ticker = row["symbol"].replace("-", ".").replace("/", "")
        take = row.get("take_profit")
        lines.append(
            'if sym == "{0}"\n'
            '    entryPrice := {1}\n'
            '    stopPrice  := {2}\n'
            '    takePrice  := {3}\n'
            '    shares     := {4}\n'
            '    entryDay   := {5}\n'.format(
                ticker, _pine_number(row["entry"]), _pine_number(row["stop"]),
                _pine_number(take if take else 0.0),
                _pine_number(row.get("shares") or 0.0, 1),
                entry_day(row.get("opened_at", ""))))
    lines.append(BODY)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED))
    parser.add_argument("--offline", action="store_true",
                        help="redraw from the last broker snapshot; do not call the broker")
    args = parser.parse_args()

    from event_aware_trader.mean_reversion import MeanReversionConfig
    config = MeanReversionConfig()

    state = Path(args.state)
    snapshot = Path(args.snapshot)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    rows = positions_and_stops(state, use_broker=not args.offline, snapshot=snapshot)
    if args.offline:
        _, taken = snapshot_holdings(snapshot)
        source = "broker snapshot of {0} UTC".format(taken or "unknown")
    else:
        source = "broker"
        write_snapshot(rows, snapshot, generated)

    take_atr, stop_atr = live_multiples(state)
    expected = expected_for(load_expected(Path(args.expected)), take_atr, stop_atr)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    adaptive = live_adaptive_config()
    out.write_text(pine_for(rows, config.rsi_exit, config.rsi_period,
                            config.max_holding_bars, expected=expected,
                            take_atr=take_atr, generated=generated, source=source,
                            take_at_broker=bool(getattr(adaptive, "take_profit_at_broker", False))),
                   encoding="utf-8")
    print("wrote {0} for {1} position(s); entry prices: {2}".format(out, len(rows), source))
    for row in rows:
        take = row["take_profit"]
        print("  {0:8} entry {1:.4f}  stop {2:.4f}  take profit {3}".format(
            row["symbol"], row["entry"], row["stop"],
            "{0:.4f}".format(take) if take else "none"))


if __name__ == "__main__":
    main()
