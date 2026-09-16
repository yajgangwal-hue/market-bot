"""Phase 5 §3, §5, §6. What was known at exactly this timestamp.

THE WHOLE POINT IS THE CLOCK. A news item may not be used because it
carries the same DATE as the trade. The frozen strategy decides in the
last twenty minutes of the session - about 19:45 UTC in summer, 20:45 in
winter - and a story published at 21:30 UTC that day is a story about
what already happened. Same date, unavailable. Joining news to trades by
date rather than by timestamp is the single easiest way to manufacture an
edge that does not exist, and it is the default behaviour of every naive
implementation.

So `Archive.snapshot(as_of, symbols)` returns only items whose publication
timestamp is strictly earlier than `as_of`, and `decision_timestamp(day)`
derives that moment from the exchange calendar rather than assuming a
fixed UTC hour across the daylight-saving boundary.

WHAT THIS ENGINE CANNOT DO, stated here rather than discovered later. It
reads a vendor archive as it exists TODAY. If a publisher silently revised
a headline after publication, the revised text is what comes back, and the
revision is invisible unless the vendor exposes an update timestamp. That
is a real look-ahead channel; `revision_risk` measures how large it is in
this archive rather than assuming it away.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

ARCHIVE = Path("data/phase5/news-archive.jsonl")

# ---------------------------------------------------------------------------
# §5. The information hierarchy
# ---------------------------------------------------------------------------

TIER1 = 1   # primary and official: filings, IR releases, government, exchange
TIER2 = 2   # established financial news with an identifiable publish time
TIER3 = 3   # secondary commentary, analyst notes, aggregation
TIER4 = 4   # unverified social or anonymous claims

TIER_NAMES = {TIER1: "primary/official", TIER2: "established financial news",
              TIER3: "secondary commentary", TIER4: "unverified"}

#: Vendors seen in this project's archive, mapped to a tier. Deliberately
#: explicit: an unrecognised source is NOT quietly treated as reputable.
SOURCE_TIERS: Dict[str, int] = {
    "sec": TIER1, "edgar": TIER1, "federalreserve": TIER1, "bls": TIER1,
    "treasury": TIER1, "bea": TIER1, "nasdaq": TIER1, "nyse": TIER1,
    "businesswire": TIER1, "globenewswire": TIER1, "prnewswire": TIER1,
    "reuters": TIER2, "bloomberg": TIER2, "wsj": TIER2, "ft": TIER2,
    "cnbc": TIER2, "marketwatch": TIER2, "barrons": TIER2, "ap": TIER2,
    "benzinga": TIER2, "yahoo_finance": TIER2, "bbc_business": TIER2,
    "fed": TIER1, "cnbc_econ": TIER2, "cnbc_top": TIER2,
    "seekingalpha": TIER3, "motleyfool": TIER3, "zacks": TIER3,
    "investorplace": TIER3, "thestreet": TIER3,
    "reddit": TIER4, "twitter": TIER4, "x": TIER4, "stocktwits": TIER4,
}

#: A blank vendor string. Alpaca's pre-2022 rows carry one, and a blank is
#: not evidence of quality in either direction - it is classified as
#: unattributed and given the aggregator's own tier, with the gap recorded.
UNATTRIBUTED = "unattributed"


def tier_for(source: Optional[str], aggregator_tier: int = TIER2) -> int:
    key = (source or "").strip().lower()
    if not key:
        return aggregator_tier
    return SOURCE_TIERS.get(key, TIER3)


# ---------------------------------------------------------------------------
# The decision clock
# ---------------------------------------------------------------------------

#: The live loop's entry window: the last 20 minutes before the 16:00 ET
#: close, so the decision is taken at about 15:45 ET.
DECISION_LOCAL = time(15, 45)


def _eastern_offset(day: date) -> timedelta:
    """UTC offset for US Eastern on a date, without a timezone database.

    US DST since 2007: second Sunday in March to first Sunday in November.
    Before 2007 it was the first Sunday in April to the last Sunday in
    October. Both rules are implemented because the thirty-year window
    reaches back to 1996 and using today's rule there would misplace the
    decision by an hour on roughly three weeks of every year.
    """
    year = day.year
    if year >= 2007:
        start = _nth_weekday(year, 3, 6, 2)      # 2nd Sunday in March
        end = _nth_weekday(year, 11, 6, 1)       # 1st Sunday in November
    else:
        start = _nth_weekday(year, 4, 6, 1)      # 1st Sunday in April
        end = _last_weekday(year, 10, 6)         # last Sunday in October
    return timedelta(hours=-4) if start <= day < end else timedelta(hours=-5)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 \
        else date(year, 12, 31)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def decision_timestamp(day: date, local: time = DECISION_LOCAL) -> datetime:
    """The UTC moment the frozen strategy decides on this session."""
    naive = datetime.combine(day, local)
    return (naive - _eastern_offset(day)).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# §3. One observation, with its provenance attached
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NewsItem:
    item_id: str
    source: str
    tier: int
    published_at: str            # ISO UTC, the vendor's publication time
    retrieved_at: Optional[str]  # when THIS project fetched it, if known
    symbols: List[str]
    headline: str
    category: str = "uncategorised"
    revised: bool = False        # vendor reports an update after publication
    usable: bool = True
    unusable_reason: str = ""

    def published(self) -> Optional[datetime]:
        return _parse(self.published_at)


def _parse(value) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def from_alpaca(raw: Dict, retrieved_at: Optional[str] = None) -> NewsItem:
    """One Alpaca news row, with its timestamp reliability assessed.

    `updated_at` later than `created_at` means the vendor changed the row
    after publishing it. The text this archive holds is therefore the
    revised text, while the timestamp used for availability is the
    original - so the item is marked revised and can be excluded wholesale
    rather than silently trusted.
    """
    created, updated = _parse(raw.get("created_at")), _parse(raw.get("updated_at"))
    source = (raw.get("source") or "").strip() or UNATTRIBUTED
    revised = bool(created and updated and (updated - created).total_seconds() > 60)
    usable, reason = True, ""
    if created is None:
        usable, reason = False, "no parseable publication timestamp"
    return NewsItem(
        item_id=str(raw.get("id")),
        source=source,
        tier=tier_for(None if source == UNATTRIBUTED else source),
        published_at=created.isoformat() if created else "",
        retrieved_at=retrieved_at,
        symbols=[str(s).upper() for s in (raw.get("symbols") or [])],
        headline=str(raw.get("headline") or ""),
        revised=revised,
        usable=usable,
        unusable_reason=reason)


# ---------------------------------------------------------------------------
# §6. The engine
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    """Everything the archive says was public before `as_of`."""
    as_of: datetime
    items: List[NewsItem] = field(default_factory=list)

    def by_tier(self, maximum_tier: int) -> List[NewsItem]:
        return [i for i in self.items if i.tier <= maximum_tier]

    def count(self, maximum_tier: int = TIER4, exclude_revised: bool = False,
              max_symbols: Optional[int] = None) -> int:
        items = self.by_tier(maximum_tier)
        if exclude_revised:
            items = [i for i in items if not i.revised]
        if max_symbols:
            items = [i for i in items if len(i.symbols) <= max_symbols]
        return len(items)

    def newest(self) -> Optional[NewsItem]:
        dated = [i for i in self.items if i.published()]
        return max(dated, key=lambda i: i.published()) if dated else None

    def hours_since_newest(self) -> Optional[float]:
        item = self.newest()
        if not item:
            return None
        return (self.as_of - item.published()).total_seconds() / 3600.0


class Archive:
    """A point-in-time news archive. Answers only about the past.

    `snapshot` is the single entry point and it is strict: an item whose
    publication timestamp is not STRICTLY before `as_of` is excluded, and
    an item with no parseable timestamp is excluded regardless of how
    interesting it looks.
    """

    def __init__(self, items: Iterable[NewsItem] = ()):
        self.items: List[NewsItem] = []
        self._by_symbol: Dict[str, List[NewsItem]] = {}
        for item in items:
            self.add(item)

    def add(self, item: NewsItem) -> None:
        self.items.append(item)
        for symbol in item.symbols:
            self._by_symbol.setdefault(symbol, []).append(item)

    @classmethod
    def load(cls, path: Path = ARCHIVE) -> "Archive":
        path = Path(path)
        archive = cls()
        if not path.exists():
            return archive
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row["symbols"] = list(row.get("symbols") or [])
                archive.add(NewsItem(**row))
        return archive

    def snapshot(self, as_of: datetime, symbols: Sequence[str] = (),
                 lookback_hours: float = 72.0) -> Snapshot:
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        floor = as_of - timedelta(hours=lookback_hours)
        pool: List[NewsItem] = []
        seen = set()
        for symbol in (symbols or self._by_symbol.keys()):
            for item in self._by_symbol.get(str(symbol).upper(), ()):
                if id(item) in seen:
                    continue
                seen.add(id(item))
                pool.append(item)
        chosen = []
        for item in pool:
            if not item.usable:
                continue
            published = item.published()
            if published is None or published >= as_of or published < floor:
                continue
            chosen.append(item)
        chosen.sort(key=lambda i: i.published())
        return Snapshot(as_of=as_of, items=chosen)

    def coverage(self) -> Dict[str, object]:
        dated = [i.published() for i in self.items if i.published()]
        return {
            "items": len(self.items),
            "symbols": len(self._by_symbol),
            "earliest": min(dated).isoformat() if dated else None,
            "latest": max(dated).isoformat() if dated else None,
            "unusable": sum(1 for i in self.items if not i.usable),
            "revised": sum(1 for i in self.items if i.revised),
            "unattributed": sum(1 for i in self.items
                                if i.source == UNATTRIBUTED),
            "by_tier": {TIER_NAMES[t]: sum(1 for i in self.items if i.tier == t)
                        for t in (TIER1, TIER2, TIER3, TIER4)},
        }


# ---------------------------------------------------------------------------
# §12. The ten information-quality questions, answered explicitly
# ---------------------------------------------------------------------------

QUESTIONS = (
    "available before the decision",
    "timestamp reliable",
    "source identifiable",
    "security correctly associated",
    "duplication across sources",
    "could contain future knowledge",
    "already reflected in the price",
    "reconstructable historically",
    "survives out-of-sample testing",
    "improves results after costs",
)


def quality_report(archive: Archive, max_symbols_for_association: int = 5
                   ) -> Dict[str, Dict[str, object]]:
    """Answer what can be answered, and say UNKNOWN where it cannot.

    An UNKNOWN here is not a formality. A feature built on a question this
    function cannot answer is flagged, and the flag travels with the
    experiment into the ledger.
    """
    items = archive.items
    n = len(items) or 1
    dated = [i for i in items if i.published()]
    attributed = [i for i in items if i.source != UNATTRIBUTED]
    tight = [i for i in items if 0 < len(i.symbols) <= max_symbols_for_association]
    headlines: Dict[str, int] = {}
    for i in items:
        key = i.headline.strip().lower()[:120]
        if key:
            headlines[key] = headlines.get(key, 0) + 1
    duplicated = sum(c - 1 for c in headlines.values() if c > 1)

    return {
        "available before the decision": {
            "answer": "ENFORCED",
            "detail": ("Archive.snapshot admits an item only when its "
                       "publication timestamp is strictly before the "
                       "decision timestamp, which is derived from the "
                       "exchange clock rather than the calendar date.")},
        "timestamp reliable": {
            "answer": "PARTIAL",
            "detail": ("{0} of {1} items carry a parseable publication time. "
                       "The time is the VENDOR's, not the primary source's, "
                       "and is not independently verifiable."
                       .format(len(dated), len(items)))},
        "source identifiable": {
            "answer": "PARTIAL",
            "detail": ("{0:.1%} of items name a vendor; the rest are "
                       "unattributed rows from the aggregator."
                       .format(len(attributed) / n))},
        "security correctly associated": {
            "answer": "WEAK",
            "detail": ("{0:.1%} of items tag {1} symbols or fewer. Tagging is "
                       "the vendor's and may be automated, so a story tagged "
                       "with a long symbol list is weak evidence about any "
                       "one of them.".format(len(tight) / n,
                                             max_symbols_for_association))},
        "duplication across sources": {
            "answer": "MEASURED",
            "detail": "{0} items share a headline with an earlier item.".format(
                duplicated)},
        "could contain future knowledge": {
            "answer": "RESIDUAL RISK",
            "detail": ("{0} items were revised after publication. The archive "
                       "stores today's text against the original timestamp, "
                       "so revised items are marked and can be excluded."
                       .format(sum(1 for i in items if i.revised)))},
        "already reflected in the price": {
            "answer": "UNKNOWN",
            "detail": "Requires the experiment, not the archive."},
        "reconstructable historically": {
            "answer": "PARTIAL",
            "detail": ("The vendor archive is queried as it exists today. A "
                       "story deleted since publication is absent and its "
                       "absence is undetectable.")},
        "survives out-of-sample testing": {
            "answer": "UNKNOWN",
            "detail": "Requires the experiment."},
        "improves results after costs": {
            "answer": "UNKNOWN",
            "detail": "Requires the experiment."},
    }
