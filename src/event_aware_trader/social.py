"""Verified-source social monitoring for paper-trading research.

Posts are fast but are not reliable enough to drive orders.  This module is
intentionally one-way: it fetches configured public posts, verifies immutable
source identities where the platform makes that possible, creates an audit-log
entry, and produces a REVIEW_REQUIRED alert.  It contains no broker code and
never infers that a public statement is true or that a price must move.
"""

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse


SUPPORTED_PLATFORMS = {"bluesky", "x", "rss"}
RUMOR_TERMS = ("rumor", "unconfirmed", "hearing that", "reportedly", "maybe", "allegedly")


@dataclass(frozen=True)
class SocialSource:
    name: str
    platform: str
    official: bool
    enabled: bool = True
    actor: str = ""
    expected_handle: str = ""
    expected_did: str = ""
    expected_author_id: str = ""
    query: str = ""
    feed_url: str = ""
    expected_domain: str = ""


@dataclass(frozen=True)
class Entity:
    ticker: str
    aliases: Tuple[str, ...]
    name: str = ""


@dataclass(frozen=True)
class SocialPost:
    post_id: str
    platform: str
    source_name: str
    author: str
    author_id: str
    text: str
    published_at: datetime
    url: str
    identity_verified: bool

    def as_dict(self) -> Dict[str, object]:
        result = asdict(self)
        result["published_at"] = self.published_at.isoformat()
        return result


@dataclass(frozen=True)
class SocialAlert:
    alert_id: str
    status: str
    trust_score: float
    post: SocialPost
    tickers: Tuple[str, ...]
    matched_aliases: Tuple[str, ...]
    reasons: Tuple[str, ...]
    requires_human_stance: bool = True
    paper_only: bool = True

    def as_dict(self) -> Dict[str, object]:
        result = asdict(self)
        result["post"] = self.post.as_dict()
        return result


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean_domain(value: str) -> str:
    return value.lower().split(":")[0]


def source_from_mapping(raw: Dict[str, object]) -> SocialSource:
    platform = str(raw.get("platform", "")).lower().strip()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError("Unsupported social platform: {0}".format(platform))
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("Each social source needs a name")
    source = SocialSource(
        name=name,
        platform=platform,
        official=bool(raw.get("official", False)),
        enabled=bool(raw.get("enabled", True)),
        actor=str(raw.get("actor", "")).strip(),
        expected_handle=str(raw.get("expected_handle", "")).strip().lower(),
        expected_did=str(raw.get("expected_did", "")).strip(),
        expected_author_id=str(raw.get("expected_author_id", "")).strip(),
        query=str(raw.get("query", "")).strip(),
        feed_url=str(raw.get("feed_url", "")).strip(),
        expected_domain=str(raw.get("expected_domain", "")).strip().lower(),
    )
    if not source.official:
        raise ValueError("Only sources independently marked official are allowed")
    if source.platform == "bluesky" and source.enabled and (not source.actor or not source.expected_did):
        raise ValueError("Enabled Bluesky sources require actor and expected_did")
    if source.platform == "x" and source.enabled and (not source.expected_author_id or not (source.actor or source.query)):
        raise ValueError("Enabled X sources require expected_author_id and actor or query")
    if source.platform == "rss" and source.enabled and (not source.feed_url or not source.expected_domain):
        raise ValueError("Enabled RSS sources require feed_url and expected_domain")
    return source


def entities_from_file(path: Path) -> List[Entity]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("entities", []) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError("Entity file must be a JSON list or an object with an 'entities' list")
    entities = []
    for entry in entries:
        ticker = str(entry.get("ticker", "")).strip().upper()
        aliases = tuple(str(value).strip().lower() for value in entry.get("aliases", []) if str(value).strip())
        if not ticker or not aliases:
            raise ValueError("Each entity needs a ticker and at least one alias")
        entities.append(Entity(ticker=ticker, aliases=aliases, name=str(entry.get("name", "")).strip()))
    return entities


def sources_from_file(path: Path) -> Tuple[List[SocialSource], Dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("sources", []) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError("Source file must be a JSON list or an object with a 'sources' list")
    settings = raw.get("settings", {}) if isinstance(raw, dict) else {}
    return [source_from_mapping(item) for item in entries], settings


def _get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout_seconds: int = 15) -> Dict[str, object]:
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "event-aware-trader/0.2 research"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def fetch_bluesky_posts(source: SocialSource, limit: int = 25) -> List[SocialPost]:
    """Use Bluesky's public author-feed endpoint with immutable DID checking."""
    parameters = urllib.parse.urlencode({"actor": source.actor, "filter": "posts_no_replies", "limit": min(limit, 100)})
    response = _get_json("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?" + parameters)
    posts = []
    for item in response.get("feed", []):
        post = item.get("post", {})
        author = post.get("author", {})
        record = post.get("record", {})
        text = str(record.get("text", "")).strip()
        post_id = str(post.get("uri", ""))
        created_at = record.get("createdAt") or post.get("indexedAt")
        if not text or not post_id or not created_at:
            continue
        handle = str(author.get("handle", "")).lower()
        did = str(author.get("did", ""))
        identity_verified = did == source.expected_did and (not source.expected_handle or handle == source.expected_handle)
        rkey = post_id.rsplit("/", 1)[-1]
        posts.append(
            SocialPost(
                post_id=post_id,
                platform="bluesky",
                source_name=source.name,
                author=handle,
                author_id=did,
                text=text,
                published_at=_parse_time(str(created_at)),
                url="https://bsky.app/profile/{0}/post/{1}".format(handle, rkey),
                identity_verified=identity_verified,
            )
        )
    return posts


def fetch_x_posts(source: SocialSource, bearer_token: str, limit: int = 25) -> List[SocialPost]:
    """Use X's official recent-search API; credentials are read only at runtime."""
    if not bearer_token:
        raise ValueError("X_BEARER_TOKEN is required for an enabled X source")
    query = source.query or "from:{0} -is:retweet -is:reply".format(source.actor.lstrip("@"))
    parameters = urllib.parse.urlencode(
        {
            "query": query,
            "max_results": min(max(limit, 10), 100),
            "tweet.fields": "created_at,author_id",
        }
    )
    response = _get_json(
        "https://api.x.com/2/tweets/search/recent?" + parameters,
        headers={"Authorization": "Bearer {0}".format(bearer_token), "User-Agent": "event-aware-trader/0.2 research"},
    )
    posts = []
    for item in response.get("data", []):
        post_id = str(item.get("id", ""))
        created_at = item.get("created_at")
        author_id = str(item.get("author_id", ""))
        text = str(item.get("text", "")).strip()
        if not post_id or not created_at or not text:
            continue
        posts.append(
            SocialPost(
                post_id="x:{0}".format(post_id),
                platform="x",
                source_name=source.name,
                author=source.actor.lstrip("@"),
                author_id=author_id,
                text=text,
                published_at=_parse_time(str(created_at)),
                url="https://x.com/{0}/status/{1}".format(source.actor.lstrip("@"), post_id),
                identity_verified=author_id == source.expected_author_id,
            )
        )
    return posts


def _rss_node(entry: ET.Element, names: Sequence[str]) -> Optional[ET.Element]:
    for name in names:
        found = entry.find(name)
        if found is not None:
            return found
    return None


def fetch_rss_posts(source: SocialSource, limit: int = 25) -> List[SocialPost]:
    """Read a configured official RSS/Atom account feed with domain pinning."""
    feed_domain = _clean_domain(urlparse(source.feed_url).netloc)
    if feed_domain != _clean_domain(source.expected_domain):
        raise ValueError("RSS source domain does not match expected_domain for {0}".format(source.name))
    request = urllib.request.Request(source.feed_url, headers={"User-Agent": "event-aware-trader/0.2 research"})
    with urllib.request.urlopen(request, timeout=15) as response:
        root = ET.fromstring(response.read())
    entries = root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
    posts = []
    for entry in entries[:limit]:
        title = _rss_node(entry, ("title", "{http://www.w3.org/2005/Atom}title"))
        description = _rss_node(entry, ("description", "summary", "{http://www.w3.org/2005/Atom}summary"))
        link = _rss_node(entry, ("link", "{http://www.w3.org/2005/Atom}link"))
        guid = _rss_node(entry, ("guid", "id", "{http://www.w3.org/2005/Atom}id"))
        date_node = _rss_node(entry, ("pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"))
        text = " ".join(value for value in ((title.text or "") if title is not None else "", (description.text or "") if description is not None else "") if value).strip()
        url = ""
        if link is not None:
            url = link.get("href", "") or (link.text or "")
        post_id = ((guid.text or "") if guid is not None else "") or url or text
        if not text or not post_id or date_node is None or not date_node.text:
            continue
        posts.append(
            SocialPost(
                post_id="rss:{0}".format(post_id),
                platform="rss",
                source_name=source.name,
                author=source.name,
                author_id=source.expected_domain,
                text=text,
                published_at=_parse_time(date_node.text.strip()),
                url=url,
                identity_verified=True,
            )
        )
    return posts


def fetch_posts(sources: Sequence[SocialSource], x_bearer_token: str = "", limit: int = 25) -> List[SocialPost]:
    posts = []
    for source in sources:
        if not source.enabled:
            continue
        if source.platform == "bluesky":
            posts.extend(fetch_bluesky_posts(source, limit))
        elif source.platform == "x":
            posts.extend(fetch_x_posts(source, x_bearer_token, limit))
        elif source.platform == "rss":
            posts.extend(fetch_rss_posts(source, limit))
    return sorted(posts, key=lambda post: post.published_at, reverse=True)


def _mention_matches(text: str, entities: Iterable[Entity]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    tickers = []
    aliases = []
    lowered = text.lower()
    for entity in entities:
        found = []
        for alias in entity.aliases:
            if re.search(r"(?<![a-z0-9]){0}(?![a-z0-9])".format(re.escape(alias)), lowered):
                found.append(alias)
        if found:
            tickers.append(entity.ticker)
            aliases.extend(found)
    return tuple(tickers), tuple(aliases)


def evaluate_post(post: SocialPost, entities: Sequence[Entity], max_post_age_minutes: int = 10, now: Optional[datetime] = None) -> SocialAlert:
    """Make a trust assessment, never a direction or an execution decision."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_minutes = (current - post.published_at.astimezone(timezone.utc)).total_seconds() / 60.0
    tickers, aliases = _mention_matches(post.text, entities)
    reasons = []
    score = 0.0
    if post.identity_verified:
        score += 75.0
        reasons.append("Configured source identity matched its pinned identifier")
    else:
        reasons.append("Source identity did not match the configured pinned identifier")
    if 0 <= age_minutes <= max_post_age_minutes:
        score += 15.0
        reasons.append("Post is {0:.1f} minutes old".format(age_minutes))
    elif age_minutes < 0:
        reasons.append("Post timestamp is in the future; hold for source-clock verification")
    else:
        reasons.append("Post is stale ({0:.1f} minutes old)".format(age_minutes))
    if tickers:
        score += 10.0
        reasons.append("Matched reviewed entity aliases: {0}".format(", ".join(aliases)))
    else:
        reasons.append("No reviewed company/entity alias matched")
    if any(term in post.text.lower() for term in RUMOR_TERMS):
        score -= 40.0
        reasons.append("Rumor-language filter triggered")
    score = max(0.0, min(100.0, score))
    status = "REVIEW_REQUIRED" if score >= 90.0 and tickers else "HOLD"
    if status == "REVIEW_REQUIRED":
        reasons.append("No trade direction inferred; verify context and choose a scenario manually")
    return SocialAlert(
        alert_id="social:{0}".format(post.post_id),
        status=status,
        trust_score=score,
        post=post,
        tickers=tickers,
        matched_aliases=aliases,
        reasons=tuple(reasons),
    )


def load_seen_post_ids(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return set(str(value) for value in raw.get("seen_post_ids", []))


def save_seen_post_ids(path: Path, post_ids: Iterable[str], max_ids: int = 5_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = list(post_ids)[-max_ids:]
    path.write_text(json.dumps({"seen_post_ids": values}, indent=2) + "\n", encoding="utf-8")


def append_alerts(path: Path, alerts: Sequence[SocialAlert]) -> None:
    if not alerts:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for alert in alerts:
            payload = {"recorded_at": datetime.now(timezone.utc).isoformat(), "kind": "social_monitor_alert", "alert": alert.as_dict()}
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def poll_once(
    sources: Sequence[SocialSource],
    entities: Sequence[Entity],
    state_path: Path,
    journal_path: Path,
    x_bearer_token: str = "",
    max_post_age_minutes: int = 10,
    limit: int = 25,
) -> List[SocialAlert]:
    seen = load_seen_post_ids(state_path)
    posts = fetch_posts(sources, x_bearer_token=x_bearer_token, limit=limit)
    unseen = [post for post in posts if post.post_id not in seen]
    alerts = [evaluate_post(post, entities, max_post_age_minutes=max_post_age_minutes) for post in unseen]
    append_alerts(journal_path, alerts)
    save_seen_post_ids(state_path, list(seen) + [post.post_id for post in posts])
    return alerts


def watch(
    sources: Sequence[SocialSource],
    entities: Sequence[Entity],
    state_path: Path,
    journal_path: Path,
    x_bearer_token: str = "",
    max_post_age_minutes: int = 10,
    poll_seconds: int = 30,
    iterations: int = 1,
) -> List[SocialAlert]:
    if poll_seconds < 5:
        raise ValueError("poll_seconds must be at least 5 to respect source limits")
    all_alerts = []
    completed = 0
    while iterations == 0 or completed < iterations:
        all_alerts.extend(
            poll_once(sources, entities, state_path, journal_path, x_bearer_token, max_post_age_minutes)
        )
        completed += 1
        if iterations == 0 or completed < iterations:
            time.sleep(poll_seconds)
    return all_alerts
