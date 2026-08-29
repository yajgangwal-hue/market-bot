"""Transparent event ingestion and scenario mapping.

This module deliberately uses auditable rules rather than presenting an opaque
headline model as a source of market truth.  An event label should be reviewed
against the cited primary source before it affects a research decision.
"""

import json
import re
from functools import lru_cache
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .types import Event


VALID_CATEGORIES = {
    "inflation",
    "central_bank",
    "energy",
    "growth",
    "geopolitics",
    "earnings",
    "other",
}
VALID_STANCES = {"hawkish", "dovish", "risk_on", "risk_off", "neutral"}

KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "inflation": ("cpi", "pce", "inflation", "consumer prices", "producer prices", "ppi"),
    "central_bank": (
        "federal reserve",
        "fed",
        "fomc",
        "central bank",
        "interest rate",
        "rate hike",
        "rate cut",
    ),
    "energy": ("oil", "crude", "opec", "hormuz", "energy supply", "refinery"),
    "growth": ("gdp", "payrolls", "nonfarm", "unemployment", "jobless claims", "recession"),
    "geopolitics": ("war", "sanctions", "invasion", "ceasefire", "blockade", "tariff"),
    "earnings": ("earnings", "guidance", "revenue", "eps", "profit warning"),
}

# Terms whose stance does NOT depend on which category matched.  "above/below
# forecast" is deliberately absent: a surprise is hawkish for a price release
# and risk-on for a growth release, so it is resolved in SURPRISE_STANCE below.
STANCE_TERMS: Dict[str, Tuple[str, ...]] = {
    "hawkish": ("rate hike", "higher for longer", "hotter", "firmer", "sticky inflation"),
    "dovish": ("rate cut", "disinflation", "cooling", "easing"),
    "risk_off": ("war", "invasion", "sanctions", "blockade", "recession", "default", "shutdown"),
    "risk_on": ("ceasefire", "stimulus", "deal reached", "soft landing"),
}

# A beat/miss only has a direction once the release is known.  Hotter inflation
# is hawkish and therefore bearish for duration and equities; hotter growth is
# risk-on.  Reading the same phrase both ways was a genuine contradiction in the
# previous table, where "above forecast" sat in the hawkish *and* risk_on lists
# and the winner depended on dictionary order rather than on evidence.
SURPRISE_TERMS: Dict[str, Tuple[str, ...]] = {
    "above": ("above forecast", "above expectations", "hotter than expected", "beats forecast"),
    "below": ("below forecast", "below expectations", "cooler than expected", "misses forecast"),
}
SURPRISE_STANCE: Dict[Tuple[str, str], str] = {
    ("inflation", "above"): "hawkish",
    ("inflation", "below"): "dovish",
    ("central_bank", "above"): "hawkish",
    ("central_bank", "below"): "dovish",
    ("growth", "above"): "risk_on",
    ("growth", "below"): "risk_off",
    ("earnings", "above"): "risk_on",
    ("earnings", "below"): "risk_off",
}

# Scenario mapping is a research hypothesis, not an estimate of future return.
# Values are capped directional alignment scores in [-1, 1].
IMPACT_MAP: Dict[Tuple[str, str], Dict[str, float]] = {
    ("inflation", "hawkish"): {"SPY": -0.35, "QQQ": -0.45, "XLK": -0.45, "XLE": 0.20, "XLF": 0.10, "TLT": -0.55, "GLD": 0.05},
    ("inflation", "dovish"): {"SPY": 0.25, "QQQ": 0.35, "XLK": 0.35, "XLE": -0.10, "XLF": -0.05, "TLT": 0.45, "GLD": 0.05},
    ("central_bank", "hawkish"): {"SPY": -0.30, "QQQ": -0.45, "XLK": -0.45, "XLE": 0.05, "XLF": 0.05, "TLT": -0.60, "GLD": -0.10},
    ("central_bank", "dovish"): {"SPY": 0.30, "QQQ": 0.45, "XLK": 0.45, "XLE": -0.05, "XLF": -0.05, "TLT": 0.60, "GLD": 0.10},
    ("energy", "risk_off"): {"SPY": -0.25, "QQQ": -0.25, "XLK": -0.20, "XLE": 0.60, "XLF": -0.10, "TLT": 0.05, "GLD": 0.25},
    ("energy", "risk_on"): {"SPY": 0.15, "QQQ": 0.15, "XLK": 0.10, "XLE": -0.45, "XLF": 0.05, "TLT": 0.00, "GLD": -0.10},
    ("growth", "risk_off"): {"SPY": -0.35, "QQQ": -0.30, "XLK": -0.25, "XLE": -0.20, "XLF": -0.30, "TLT": 0.35, "GLD": 0.20},
    ("growth", "risk_on"): {"SPY": 0.35, "QQQ": 0.30, "XLK": 0.25, "XLE": 0.20, "XLF": 0.30, "TLT": -0.35, "GLD": -0.10},
    ("geopolitics", "risk_off"): {"SPY": -0.40, "QQQ": -0.35, "XLK": -0.30, "XLE": 0.30, "XLF": -0.20, "TLT": 0.20, "GLD": 0.45},
    ("geopolitics", "risk_on"): {"SPY": 0.20, "QQQ": 0.20, "XLK": 0.15, "XLE": -0.15, "XLF": 0.10, "TLT": -0.10, "GLD": -0.25},
    ("earnings", "risk_on"): {"SPY": 0.10, "QQQ": 0.20, "XLK": 0.20, "XLE": 0.00, "XLF": 0.00, "TLT": 0.00, "GLD": 0.00},
    ("earnings", "risk_off"): {"SPY": -0.10, "QQQ": -0.20, "XLK": -0.20, "XLE": 0.00, "XLF": 0.00, "TLT": 0.00, "GLD": 0.00},
}


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            raise ValueError("Unsupported timestamp: {0}".format(value))


def _normalise_timestamp(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> "re.Pattern[str]":
    """Compile a whole-word matcher for one keyword.

    Plain substring matching was the single largest source of false labels:
    "fed" matched FedEx, "war" matched software and warehouse, and "ppi"
    matched shipping.  Those are not near-misses - a benign product headline
    was being scored as a risk-off geopolitical event.  Word boundaries with
    flexible internal whitespace keep multi-word terms such as "rate hike"
    working while removing the accidental matches.  Results are cached because
    a screening run classifies the same feed terms thousands of times.
    """
    escaped = r"\s+".join(re.escape(part) for part in term.split())
    return re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)


def _terms_in(text: str, terms: Iterable[str]) -> List[str]:
    return [term for term in terms if _term_pattern(term).search(text)]


def classify_headline(title: str, published_at: Optional[datetime] = None, source: str = "", url: str = "") -> Event:
    """Create a conservative, review-required label for a headline.

    It chooses a category only when it finds category terms.  Stance defaults to
    neutral because a headline alone often omits the benchmark and context.
    """
    category_hits = {category: _terms_in(title, terms) for category, terms in KEYWORDS.items()}
    category, matched = max(category_hits.items(), key=lambda pair: len(pair[1]))
    if not matched:
        category = "other"

    stance_hits = {stance: _terms_in(title, terms) for stance, terms in STANCE_TERMS.items()}
    ranked = sorted(stance_hits.items(), key=lambda pair: len(pair[1]), reverse=True)
    stance, stance_matches = ranked[0]
    if not stance_matches:
        stance, stance_matches = "neutral", []

    # A beat/miss is only directional once the release type is known.
    surprise_matches: List[str] = []
    for direction, terms in SURPRISE_TERMS.items():
        hits = _terms_in(title, terms)
        if hits:
            surprise_matches.extend(hits)
            resolved = SURPRISE_STANCE.get((category, direction))
            if resolved and not stance_matches:
                stance = resolved

    # An unresolved tie between two opposing stances is reported rather than
    # silently decided by dictionary order.  The caller must review it.
    contested = [name for name, hits in ranked[1:] if hits and len(hits) == len(stance_matches)]
    conflict = bool(stance_matches and contested)

    notes = "Automatic RSS label; review against a primary source before using it."
    if conflict:
        notes = (
            "CONTRADICTORY: '{0}' and '{1}' both matched equally; stance forced to neutral. {2}"
        ).format(stance, contested[0], notes)
        stance = "neutral"

    confidence = 0.2 if category == "other" else min(
        0.55, 0.25 + 0.1 * len(matched) + 0.05 * len(stance_matches)
    )
    if conflict:
        confidence = min(confidence, 0.2)

    return Event(
        title=title,
        category=category,
        stance=stance,
        confidence=confidence,
        published_at=published_at,
        source=source,
        url=url,
        notes=notes,
        matched_terms=matched + stance_matches + surprise_matches,
    )


def event_from_mapping(raw: Dict[str, object]) -> Event:
    category = str(raw.get("category", "other")).lower()
    stance = str(raw.get("stance", "neutral")).lower()
    if category not in VALID_CATEGORIES:
        raise ValueError("Unsupported event category: {0}".format(category))
    if stance not in VALID_STANCES:
        raise ValueError("Unsupported event stance: {0}".format(stance))
    confidence = float(raw.get("confidence", 0.5))
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Event confidence must be between 0 and 1")
    title = str(raw.get("title", "")).strip()
    if not title:
        raise ValueError("Each event needs a title")
    return Event(
        title=title,
        category=category,
        stance=stance,
        confidence=confidence,
        published_at=_parse_datetime(raw.get("published_at")),
        scheduled_at=_parse_datetime(raw.get("scheduled_at")),
        source=str(raw.get("source", "")),
        url=str(raw.get("url", "")),
        notes=str(raw.get("notes", "")),
        matched_terms=[str(term) for term in raw.get("matched_terms", [])],
    )


def load_events(path: Path) -> List[Event]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("events", []) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError("Event file must be a JSON list or an object with an 'events' list")
    return [event_from_mapping(item) for item in entries]


def save_events(path: Path, events: Sequence[Event]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"events": [event.as_dict() for event in events]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _event_is_available(event: Event, as_of: datetime) -> bool:
    if event.published_at is None:
        return True
    published = _normalise_timestamp(event.published_at)
    current = _normalise_timestamp(as_of)
    return bool(published and current and published <= current)


def active_event_impact(symbol: str, events: Sequence[Event], as_of: datetime, max_age_days: int = 5) -> Tuple[float, List[str]]:
    """Return a confidence- and recency-weighted scenario alignment.

    Scheduled events are intentionally excluded: they create a blackout rather
    than a directional bet.  Events without a public timestamp receive a 0.5
    weight because their historical availability cannot be verified.
    """
    total = 0.0
    evidence = []
    as_of_utc = _normalise_timestamp(as_of)
    for event in events:
        if event.scheduled_at is not None or not _event_is_available(event, as_of):
            continue
        mapping = IMPACT_MAP.get((event.category, event.stance), {})
        raw_impact = mapping.get(symbol.upper(), 0.0)
        if raw_impact == 0:
            continue
        if event.published_at is None:
            freshness = 0.5
        else:
            published = _normalise_timestamp(event.published_at)
            age_days = max(0.0, (as_of_utc - published).total_seconds() / 86400.0) if as_of_utc and published else max_age_days
            freshness = max(0.0, 1.0 - age_days / max_age_days)
        contribution = raw_impact * event.confidence * freshness
        total += contribution
        evidence.append("{0}: {1:+.2f}".format(event.title, contribution))
    return max(-1.0, min(1.0, total)), evidence


def in_event_blackout(as_of: datetime, events: Sequence[Event], blackout_minutes: int = 90) -> Optional[Event]:
    current = _normalise_timestamp(as_of)
    if current is None:
        return None
    window = timedelta(minutes=blackout_minutes)
    for event in events:
        scheduled = _normalise_timestamp(event.scheduled_at)
        if scheduled and abs(current - scheduled) <= window:
            return event
    return None


def fetch_rss_events(feed_url: str, max_items: int = 20, timeout_seconds: int = 15) -> List[Event]:
    """Fetch an RSS/Atom feed into a review queue; no credentials are stored."""
    request = urllib.request.Request(feed_url, headers={"User-Agent": "event-aware-trader/0.1 research"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        document = response.read()
    root = ET.fromstring(document)
    entries = root.findall(".//item")
    if not entries:  # Atom feeds
        entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    events: List[Event] = []
    for entry in entries[:max_items]:
        title_node = entry.find("title")
        if title_node is None:
            title_node = entry.find("{http://www.w3.org/2005/Atom}title")
        title = title_node.text.strip() if title_node is not None and title_node.text else ""
        link_node = entry.find("link")
        if link_node is None:
            link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        link = ""
        if link_node is not None:
            link = link_node.get("href", "") or (link_node.text or "")
        date_node = entry.find("pubDate")
        if date_node is None:
            date_node = entry.find("published")
        if date_node is None:
            date_node = entry.find("updated")
        if date_node is None:
            date_node = entry.find("{http://www.w3.org/2005/Atom}published")
        if date_node is None:
            date_node = entry.find("{http://www.w3.org/2005/Atom}updated")
        published = _parse_datetime(date_node.text.strip()) if date_node is not None and date_node.text else None
        if title:
            events.append(classify_headline(title, published_at=published, source=feed_url, url=link))
    return events
