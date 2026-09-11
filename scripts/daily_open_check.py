"""How closely does the daily bar's open track the 09:30 auction? Distribution.

The previous check asked a yes/no question of noisy price data and answered
VOID because one row of twelve differed by 0.09%. That was the wrong
instrument: eight of the twelve matched to four decimal places, which a
pre-market price could never do. The finding was nearly discarded by a bad
threshold rather than by evidence.

So this measures the DISTRIBUTION across many symbols and sessions, and
compares it against the pre-market price as a control. If the daily open
tracks 09:30 tightly and the 04:00 price does not, the question is settled and
the size of the residual noise is known rather than guessed - which matters,
because the overnight edge being tested is itself only 0.12% to 0.29%.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
KEY = os.environ.get("APCA_API_KEY_ID", "").strip()
SECRET = os.environ.get("APCA_API_SECRET_KEY", "").strip()
HEADERS = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}
SYMBOLS = ["AAPL", "SPY", "TJX", "COST", "RTX", "LIN", "XHB", "VNQ",
           "MSFT", "JNJ", "XOM", "WMT"]
START = "2026-06-01"


def get(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch(timeframe, limit):
    rows = {}
    token = None
    while True:
        url = ("https://data.alpaca.markets/v2/stocks/bars?symbols={0}"
               "&timeframe={1}&start={2}&limit={3}&adjustment=split".format(
                   urllib.parse.quote(",".join(SYMBOLS)), timeframe, START, limit))
        if token:
            url += "&page_token=" + urllib.parse.quote(token)
        payload = get(url)
        for symbol, bars in (payload.get("bars") or {}).items():
            rows.setdefault(symbol, []).extend(bars)
        token = payload.get("next_page_token")
        if not token:
            break
    return rows


daily = fetch("1Day", 1000)
intraday = fetch("15Min", 10000)

session_open, premarket_open = {}, {}
for symbol, bars in intraday.items():
    for row in bars:
        local = datetime.fromisoformat(
            row["t"].replace("Z", "+00:00")).astimezone(EASTERN)
        key = (symbol, local.date())
        minutes = local.hour * 60 + local.minute
        if minutes == 570:
            session_open[key] = float(row["o"])
        if key not in premarket_open:
            premarket_open[key] = float(row["o"])

to_session, to_premarket = [], []
exact = 0
for symbol, bars in daily.items():
    for row in bars:
        local = datetime.fromisoformat(
            row["t"].replace("Z", "+00:00")).astimezone(EASTERN)
        key = (symbol, local.date())
        opening = session_open.get(key)
        early = premarket_open.get(key)
        if not opening or not early:
            continue
        daily_open = float(row["o"])
        to_session.append(abs(daily_open / opening - 1.0))
        to_premarket.append(abs(daily_open / early - 1.0))
        if abs(daily_open - opening) < 1e-6:
            exact += 1

n = len(to_session)
print("{0} symbol-sessions compared\n".format(n))
if n < 50:
    print("too few to judge")
    raise SystemExit(1)

print("{0:<34}{1:>12}{2:>12}{3:>12}".format(
    "daily open vs...", "median gap", "mean gap", "90th pct"))
print("-" * 70)
for label, values in (("the 09:30 REGULAR-session open", to_session),
                      ("the 04:00 PRE-MARKET open", to_premarket)):
    values_sorted = sorted(values)
    print("{0:<34}{1:>12.4%}{2:>12.4%}{3:>12.4%}".format(
        label, median(values_sorted), sum(values) / len(values),
        values_sorted[int(len(values_sorted) * 0.9)]))

print("\nexact matches to the 09:30 open: {0} of {1}  ({2:.0%})".format(
    exact, n, exact / n))
print("\nA pre-market price cannot match the 09:30 auction exactly. If the")
print("exact-match rate is high and the gap to 09:30 is far smaller than the")
print("gap to 04:00, the daily open IS the regular-session open.")
