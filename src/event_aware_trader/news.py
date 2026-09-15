"""Point-in-time news, recorded as it arrives and not traded on.

WHY RECORDED AND NOT TRADED ON. The account owner asked for the bot to use
current news - the example being that Apple launching new phones should be a
reason to buy. That was measured before anything was built (EXP-0040/0041,
ten Apple September launches 2016-2025, event dates derived from this same
API rather than recalled):

    30 sessions BEFORE the launch   +5.11% mean, positive 9 of 10
    buying ON the launch day, +1d   -0.58% mean, positive 3 of 10
                              +5d   -0.33% mean, positive 4 of 10
                             +20d   +0.78% mean, positive 6 of 10

The drift lands before the event, because a scheduled launch is modelled by
everyone weeks ahead. Buying the headline is the wrong half of the trade, so
no headline reaches an entry or an exit decision here.

WHY RECORD IT AT ALL, THEN. Because a news signal cannot be tested honestly
on news you did not have at the time. Alpaca serves history back to 2016, but
a historical feed is revised, back-filled and survivorship-prone in ways that
are invisible afterwards - the same trap that made the overnight-gapper book
look like 23.6% a year until it was run on a universe that could not delist.
Recording what the bot could actually see, with the timestamp it saw it, is
the only way to build a corpus that a later test can trust. Every row carries
`fetched_at` alongside the publisher's `created_at` for exactly that reason.

The classification reuses `events.classify_headline`, which is conservative
by design: it assigns a category only when it finds category terms and
defaults to a neutral stance, because a headline alone usually omits the
benchmark and the context.
"""

import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .events import classify_headline
from .types import Event

NEWS_URL = "https://data.alpaca.markets/v1beta1/news"

# Sources beyond Alpaca. Each was REACHED and parsed on 2026-09-15 before
# being listed here; feeds that did not respond are recorded with the reason
# so nobody re-adds them hopefully. Reuters' public RSS no longer resolves at
# all, BLS returns 404 and Treasury times out from this machine.
#
# Alpaca is per-symbol and is what ties a story to a position. These are
# macro and market-wide: the 10-year yield, the Fed, the data calendar - the
# context that moves a whole book at once rather than one name.
RSS_SOURCES = (
    ("fed", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("cnbc_econ", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("cnbc_top", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("yahoo_finance", "https://finance.yahoo.com/news/rssindex"),
    ("marketwatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("bbc_business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
)
UNREACHABLE = {
    "reuters": "public RSS retired; DNS no longer resolves",
    "bls": "HTTP 404",
    "treasury": "read timeout from this machine",
}

RSS_AGENT = "market-bot research (paper trading, non-commercial)"
NEWS_DIR = Path("data/news")

# Alpaca's cap per request. Paging beyond a few hundred items per symbol per
# day is pointless for a daily record and burns rate limit.
PAGE = 50
MAX_PAGES = 10


def _headers() -> Dict[str, str]:
    key = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        raise RuntimeError(
            "News needs APCA_API_KEY_ID and APCA_API_SECRET_KEY in the "
            "environment, the same keys the broker uses.")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def fetch_news(symbols: Sequence[str], start: str, end: str,
               opener=None) -> List[Dict[str, object]]:
    """Raw news items for `symbols` between two ISO dates, following pages.

    `opener` is injected by the tests so the paging and error handling can be
    exercised without a network or credentials.
    """
    if not symbols:
        return []
    opener = opener or _open
    out: List[Dict[str, object]] = []
    page: Optional[str] = None
    for _ in range(MAX_PAGES):
        query = {"symbols": ",".join(symbols), "start": start, "end": end,
                 "limit": PAGE}
        if page:
            query["page_token"] = page
        body = opener(NEWS_URL + "?" + urllib.parse.urlencode(query))
        out.extend(body.get("news", []) or [])
        page = body.get("next_page_token")
        if not page:
            break
    return out


def fetch_rss(name: str, url: str, opener=None) -> List[Dict[str, object]]:
    """One RSS/Atom feed, shaped exactly like an Alpaca news item.

    Same shape on purpose: `record` then treats every source identically and
    the corpus has one schema rather than one per publisher. `symbols` is
    empty because a macro headline is not about a ticker - saying otherwise
    would invent a link a later study would then find.
    """
    opener = opener or _open_raw
    try:
        raw = opener(url)
    except Exception:                      # network, DNS, timeout, HTTP error
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    ATOM = "{http://www.w3.org/2005/Atom}"
    items = root.findall(".//item") or root.findall(".//" + ATOM + "entry")
    out = []
    for node in items:
        title = (node.findtext("title") or node.findtext(ATOM + "title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not link:
            holder = node.find(ATOM + "link")
            link = holder.get("href", "") if holder is not None else ""
        stamp = (node.findtext("pubDate") or node.findtext("published")
                 or node.findtext(ATOM + "updated") or "")
        if not title:
            continue
        out.append({
            # The link is the stable identity across refetches; a feed that
            # renumbers its own guids would otherwise duplicate every cycle.
            "id": "{0}:{1}".format(name, link or title),
            "headline": title,
            "created_at": _rss_time(stamp),
            "symbols": [],
            "source": name,
            "url": link,
        })
    return out


def _rss_time(value: str) -> Optional[str]:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        pass
    parsed = _parse(value)
    return parsed.isoformat() if parsed else None


def _open_raw(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": RSS_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def fetch_all_rss(sources=RSS_SOURCES, opener=None) -> List[Dict[str, object]]:
    """Every configured feed. A source that fails is skipped, not fatal."""
    out = []
    for name, url in sources:
        out.extend(fetch_rss(name, url, opener=opener))
    return out


def _open(url: str) -> Dict[str, object]:
    request = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _parse(stamp: Optional[str]) -> Optional[datetime]:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def to_events(items: Iterable[Dict[str, object]]) -> List[Event]:
    """Classify each headline with the module the rest of the project uses."""
    events = []
    for item in items:
        title = str(item.get("headline") or "").strip()
        if not title:
            continue
        events.append(classify_headline(
            title, published_at=_parse(item.get("created_at")),
            source=str(item.get("source") or "alpaca"),
            url=str(item.get("url") or "")))
    return events


def record(items: Sequence[Dict[str, object]], directory: Path = NEWS_DIR,
           fetched_at: Optional[datetime] = None) -> Path:
    """Append today's items to a dated file, point-in-time.

    Append-only, and every row carries the moment it was FETCHED as well as
    the publisher's timestamp. A later backtest can then replay only what was
    actually visible by a given instant, which is the whole reason this file
    exists rather than a query against the vendor's current history.

    Duplicates are dropped within a file by the item id, so a loop that runs
    every fifteen minutes does not write the same headline ninety-six times.
    """
    fetched_at = fetched_at or datetime.now(timezone.utc)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (fetched_at.date().isoformat() + ".jsonl")

    seen = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    seen.add(json.loads(line).get("id"))
                except json.JSONDecodeError:
                    continue

    written = 0
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            ident = item.get("id")
            if ident in seen:
                continue
            # A story with no headline has nothing to classify and nothing a
            # reader could check against a primary source. Recording it would
            # only inflate the counts a later test might key on.
            if not str(item.get("headline") or "").strip():
                continue
            seen.add(ident)
            event = to_events([item])
            row = {
                "id": ident,
                "fetched_at": fetched_at.isoformat(),
                "created_at": item.get("created_at"),
                "symbols": item.get("symbols") or [],
                "headline": item.get("headline"),
                "source": item.get("source"),
                "url": item.get("url"),
            }
            if event:
                row["category"] = event[0].category
                row["stance"] = event[0].stance
                row["matched_terms"] = event[0].matched_terms
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            written += 1
    return path


def load_day(day: date, directory: Path = NEWS_DIR) -> List[Dict[str, object]]:
    path = Path(directory) / (day.isoformat() + ".jsonl")
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def visible_at(rows: Sequence[Dict[str, object]],
               moment: datetime) -> List[Dict[str, object]]:
    """Only the rows already fetched by `moment` - the point-in-time view.

    This is the function a future backtest must go through. Filtering on the
    publisher's `created_at` instead would quietly admit stories that were
    revised or back-filled after the fact, which is the leak this whole file
    exists to prevent.
    """
    out = []
    for row in rows:
        stamp = _parse(row.get("fetched_at"))
        if stamp is not None and stamp <= moment:
            out.append(row)
    return out
