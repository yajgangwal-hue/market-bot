"""Generate a TradingView indicator showing the bot's REAL live exit levels.

WHY THIS IS GENERATED RATHER THAN WRITTEN ONCE

Pine Script cannot fetch external data. There is no way for a TradingView
indicator to ask this machine what the bot currently holds, so the levels have
to be baked into the script and the script regenerated whenever they change.
`session-run.ps1` calls this every cycle, so the file on disk is always
current; TradingView shows the new values once the script is re-pasted or the
saved indicator is updated.

WHAT IT DRAWS, AND THE ONE THING IT DELIBERATELY DOES NOT

  RED ZONE         entry down to the stop, shaded. This is the real risk:
                   what the position can lose before the broker's resting GTC
                   stop closes it. A fixed, known number.
  GREEN ZONE       the region above entry, mirrored to the same height as the
                   risk zone so the two are visually comparable. It is NOT a
                   take-profit - see below - it is simply where the position
                   is in profit.
  stop loss        a real, fixed price. Drawn as a solid line with a label.
  entry            where the position was opened.
  RSI exit         the rule closes when RSI(14) >= 60. Pine computes RSI
                   itself, so this is drawn live rather than baked in - the
                   chart shades the bars where the bot would be selling.
  holding cap      the rule closes after 20 trading days. Drawn as a vertical
                   line at the expiry session.

  TAKE PROFIT      not drawn, because the bot does not have one.

That last point is the reason this file exists rather than a simpler one. The
entry order carries a take-profit leg purely so Alpaca will accept it as a
bracket, and `_reconcile_protective_stops` deliberately cancels that leg on
the next cycle - the comment there explains why: the simulator never exits on
a target under the shipped exit mode, so a live take-profit would close
positions the backtest held, and the measured edge would stop describing what
the account actually does. Drawing a take-profit line would show a level the
bot will never act on, which is worse than showing nothing.
"""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "tradingview" / "live-levels.pine"

HEADER = '''// ============================================================
// Bot live levels - GENERATED, do not edit by hand
// Regenerated {generated} UTC by scripts/tradingview_levels.py
// ------------------------------------------------------------
// Pine Editor -> New indicator -> select all -> paste -> Save
// -> Add to chart. Re-paste after the bot opens or closes a
// position; Pine cannot read this machine, so the numbers are
// baked in at generation time.
//
// Positions represented: {count}
//
// NOTE ON TAKE PROFITS. The bot does not have one. It exits on
// the stop, on RSI(14) >= {rsi_exit:.0f}, or after {hold} trading days. The
// bracket sent with an entry carries a take-profit leg only so
// Alpaca will accept the order, and the next cycle cancels it -
// see _reconcile_protective_stops. A take-profit line would
// show a level the bot will never act on, so none is drawn.
// ============================================================
//@version=6
indicator("Bot Live Levels", overlay=true)

rsiExit  = input.float({rsi_exit}, "RSI exit level", group="Rule")
rsiLen   = input.int({rsi_len},  "RSI length",      group="Rule")
holdBars = input.int({hold}, "Holding cap (sessions)", group="Rule")
showZone = input.bool(true, "Shade the RSI exit zone", group="Display")

sym = syminfo.ticker

entryPrice = 0.0
stopPrice  = 0.0
entryMs    = 0
'''

BODY = '''
strength = ta.rsi(close, rsiLen)

// ---- the ZONES: shaded areas, not just lines ---------------------------------
// Asked for directly: the red and green regions a trader expects to see.
//
// RED is the real risk: entry down to the stop. That area is what this
// position can lose before the broker's resting GTC stop closes it, and it is
// a genuine, fixed, known number.
//
// GREEN is NOT a take-profit, because this strategy does not have one. It is
// the region above entry - where the position is in profit - drawn to the
// same height as the risk zone so the two are visually comparable. Reading it
// as a target would be reading in something the bot will never act on.
var box riskBox = na
var box gainBox = na
var line stopLine = na
var line entryLine = na
var label stopLabel = na
var label entryLabel = na

// One block, not two. Pine scopes a variable to the if it is declared in, but
// two blocks each declaring `left` is a needless invitation to a compile error
// in a file that cannot be compiled here before it reaches the chart.
if barstate.islast and stopPrice > 0
    if not na(riskBox)
        box.delete(riskBox)
        box.delete(gainBox)
    if not na(stopLine)
        line.delete(stopLine)
        line.delete(entryLine)
        label.delete(stopLabel)
        label.delete(entryLabel)
    left = bar_index - 120
    right = bar_index + 20
    riskBox := box.new(left, entryPrice, right, stopPrice,
         border_color=color.new(color.red, 40),
         bgcolor=color.new(color.red, 88),
         xloc=xloc.bar_index)
    // Mirror the risk height upward. Same distance, opposite direction.
    gainBox := box.new(left, entryPrice + (entryPrice - stopPrice), right, entryPrice,
         border_color=color.new(color.green, 40),
         bgcolor=color.new(color.green, 90),
         xloc=xloc.bar_index)
    stopLine := line.new(left, stopPrice, bar_index + 20, stopPrice,
         xloc=xloc.bar_index, color=color.new(color.red, 0), width=2)
    entryLine := line.new(left, entryPrice, bar_index + 20, entryPrice,
         xloc=xloc.bar_index, color=color.new(color.gray, 30), width=1,
         style=line.style_dashed)
    stopLabel := label.new(bar_index + 20, stopPrice,
         "STOP  " + str.tostring(stopPrice, format.mintick),
         xloc=xloc.bar_index, style=label.style_label_left,
         color=color.new(color.red, 85), textcolor=color.red, size=size.small)
    entryLabel := label.new(bar_index + 20, entryPrice,
         "entry " + str.tostring(entryPrice, format.mintick),
         xloc=xloc.bar_index, style=label.style_label_left,
         color=color.new(color.gray, 90), textcolor=color.gray, size=size.small)

// ---- the RSI exit: computed live, because Pine can ---------------------------
// This is the exit that actually closes most positions. It is not a price, so
// it cannot be a horizontal line - it is a CONDITION, and the honest way to
// draw it is to mark the bars where it holds.
inExitZone = stopPrice > 0 and strength >= rsiExit
bgcolor(showZone and inExitZone ? color.new(color.green, 88) : na,
     title="RSI exit zone")
plotshape(stopPrice > 0 and strength >= rsiExit and strength[1] < rsiExit,
     title="RSI exit triggers", style=shape.triangledown, location=location.abovebar,
     color=color.new(color.green, 0), size=size.tiny, text="exit")

// ---- the holding cap ---------------------------------------------------------
var line capLine = na
if barstate.islast and entryMs > 0
    if not na(capLine)
        line.delete(capLine)
    // Sessions elapsed since entry, counted on the chart's own bars.
    held = 0
    for i = 0 to math.min(bar_index, 600)
        if time[i] >= entryMs
            held += 1
    remaining = holdBars - held
    capX = bar_index + math.max(remaining, 0)
    capLine := line.new(capX, low * 0.97, capX, high * 1.03,
         xloc=xloc.bar_index, color=color.new(color.orange, 20), width=1,
         style=line.style_dotted,
         extend=extend.both)

// ---- a plain summary, so the numbers are readable without hovering -----------
var table panel = table.new(position.top_right, 2, 5, border_width=1)
if barstate.islast
    table.cell(panel, 0, 0, "Bot", text_color=color.white,
         bgcolor=color.new(color.blue, 40), text_size=size.small)
    table.cell(panel, 1, 0, stopPrice > 0 ? "HOLDING" : "no position",
         text_color=color.white, bgcolor=color.new(color.blue, 40),
         text_size=size.small)
    table.cell(panel, 0, 1, "entry", text_size=size.small)
    table.cell(panel, 1, 1, stopPrice > 0 ? str.tostring(entryPrice, format.mintick) : "-",
         text_size=size.small)
    table.cell(panel, 0, 2, "stop", text_size=size.small)
    table.cell(panel, 1, 2, stopPrice > 0 ? str.tostring(stopPrice, format.mintick) : "-",
         text_color=color.red, text_size=size.small)
    table.cell(panel, 0, 3, "risk to stop", text_size=size.small)
    table.cell(panel, 1, 3, stopPrice > 0
         ? str.tostring((entryPrice - stopPrice) / entryPrice * 100, "#.0") + "%"
         : "-", text_color=color.red, text_size=size.small)
    table.cell(panel, 0, 4, "RSI now", text_size=size.small)
    table.cell(panel, 1, 4, str.tostring(strength, "#.0") + " / " + str.tostring(rsiExit, "#"),
         text_color=strength >= rsiExit ? color.green : color.gray, text_size=size.small)
'''


def positions_and_stops(state_file: Path, use_broker: bool):
    """What the bot holds, and the stop it recorded when it opened each one.

    The broker is the authority on WHAT is held - a position closed by hand
    elsewhere must not appear on the chart - and local state is the authority
    on the stop PRICE, because that is an entry-time fact the broker does not
    report back.
    """
    stops = {}
    if state_file.exists():
        try:
            stops = json.loads(state_file.read_text(encoding="utf-8")).get("stops", {})
        except (OSError, ValueError):
            stops = {}

    held = {}
    if use_broker:
        from event_aware_trader.broker import AlpacaPaperBroker
        for position in AlpacaPaperBroker().positions():
            held[str(position["symbol"])] = float(position["average_entry_price"])
    else:
        for symbol, entry in stops.items():
            held[symbol] = float(entry.get("entry", 0.0))

    rows = []
    for symbol in sorted(held):
        recorded = stops.get(symbol) or {}
        stop = recorded.get("current") or recorded.get("initial")
        if not stop:
            continue
        rows.append({
            "symbol": symbol,
            "entry": held[symbol],
            "stop": float(stop),
            "opened_at": recorded.get("opened_at_ts") or "",
        })
    return rows


def pine_for(rows, rsi_exit, rsi_len, hold):
    lines = [HEADER.format(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        count=len(rows), rsi_exit=rsi_exit, rsi_len=rsi_len, hold=hold)]
    if not rows:
        lines.append("// The bot holds nothing right now, so no levels are set.\n")
    for row in rows:
        # Pine has no dictionaries, so the held symbols become a chain of
        # comparisons against the charted ticker. TradingView spells a share
        # class "BRK.B" where this project says "BRK-B".
        ticker = row["symbol"].replace("-", ".").replace("/", "")
        stamp = 0
        if row["opened_at"]:
            try:
                text = row["opened_at"].replace("Z", "+00:00")
                when = datetime.fromisoformat(text)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                stamp = int(when.timestamp() * 1000)
            except ValueError:
                stamp = 0
        lines.append(
            'if sym == "{0}"\n'
            '    entryPrice := {1:.4f}\n'
            '    stopPrice  := {2:.4f}\n'
            '    entryMs    := {3}\n'.format(ticker, row["entry"], row["stop"], stamp))
    lines.append(BODY)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--state", default=str(REPO / "data" / "autotrade-state.json"))
    parser.add_argument("--offline", action="store_true",
                        help="use local state only; do not call the broker")
    args = parser.parse_args()

    from event_aware_trader.mean_reversion import MeanReversionConfig
    config = MeanReversionConfig()

    rows = positions_and_stops(Path(args.state), use_broker=not args.offline)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pine_for(rows, config.rsi_exit, config.rsi_period,
                            config.max_holding_bars), encoding="utf-8")
    print("wrote {0} for {1} position(s)".format(out, len(rows)))
    for row in rows:
        print("  {0:8} entry {1:.2f}  stop {2:.2f}".format(
            row["symbol"], row["entry"], row["stop"]))


if __name__ == "__main__":
    main()
