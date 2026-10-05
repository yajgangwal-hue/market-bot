"""Point-in-time news recording.

The property that matters is `visible_at`: a backtest must only ever see what
had actually been fetched by the moment it is simulating. Filtering on the
publisher's timestamp instead would admit back-filled and revised stories,
which is the leak that makes news backtests lie.
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.news import (
    NEWS_URL, fetch_news, load_day, record, to_events, visible_at)

NOW = datetime(2026, 9, 14, 20, 0, tzinfo=timezone.utc)


def item(ident, headline, created, symbols=("AAPL",)):
    return {"id": ident, "headline": headline, "created_at": created,
            "symbols": list(symbols), "source": "benzinga",
            "url": "https://example.test/" + str(ident)}


class Recording(unittest.TestCase):
    def test_a_row_carries_when_it_was_fetched_not_only_when_published(self):
        with TemporaryDirectory() as tmp:
            path = record([item(1, "Apple launches foldable iPhone",
                                "2026-09-12T14:00:00Z")], Path(tmp), NOW)
            rows = [json.loads(l) for l in path.read_text().splitlines()]
            self.assertEqual(rows[0]["created_at"], "2026-09-12T14:00:00Z")
            self.assertEqual(rows[0]["fetched_at"], NOW.isoformat())
            self.assertEqual(rows[0]["symbols"], ["AAPL"])

    def test_the_headline_is_classified_by_the_shared_classifier(self):
        with TemporaryDirectory() as tmp:
            path = record([item(1, "Fed raises interest rate as inflation cools",
                                "2026-09-14T13:00:00Z")], Path(tmp), NOW)
            row = json.loads(path.read_text().splitlines()[0])
            self.assertIn(row["category"], ("central_bank", "inflation"))
            self.assertIn("stance", row)

    def test_the_same_story_is_not_written_twice(self):
        with TemporaryDirectory() as tmp:
            one = item(7, "Apple launches foldable iPhone", "2026-09-12T14:00:00Z")
            record([one], Path(tmp), NOW)
            record([one], Path(tmp), NOW + timedelta(minutes=15))
            record([one, item(8, "Another story", "2026-09-14T15:00:00Z")],
                   Path(tmp), NOW + timedelta(minutes=30))
            rows = load_day(NOW.date(), Path(tmp))
            self.assertEqual(len(rows), 2)
            self.assertEqual(sorted(r["id"] for r in rows), [7, 8])

    def test_a_headline_with_no_text_is_skipped(self):
        with TemporaryDirectory() as tmp:
            record([item(1, "   ", "2026-09-14T13:00:00Z")], Path(tmp), NOW)
            self.assertEqual(load_day(NOW.date(), Path(tmp)), [])

    def test_a_missing_day_is_empty_not_an_error(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(load_day(date(2020, 1, 1), Path(tmp)), [])


class PointInTime(unittest.TestCase):
    def test_only_what_had_been_fetched_is_visible(self):
        rows = [
            {"id": 1, "fetched_at": "2026-09-14T14:00:00+00:00"},
            {"id": 2, "fetched_at": "2026-09-14T18:00:00+00:00"},
            {"id": 3, "fetched_at": "2026-09-14T21:00:00+00:00"},
        ]
        seen = visible_at(rows, datetime(2026, 9, 14, 19, tzinfo=timezone.utc))
        self.assertEqual([r["id"] for r in seen], [1, 2])

    def test_the_boundary_is_inclusive(self):
        rows = [{"id": 1, "fetched_at": "2026-09-14T19:00:00+00:00"}]
        at = datetime(2026, 9, 14, 19, tzinfo=timezone.utc)
        self.assertEqual(len(visible_at(rows, at)), 1)

    def test_a_row_without_a_fetch_time_is_never_visible(self):
        # Safer to drop it than to guess: an unknown fetch time could be a
        # back-filled story, which is exactly what must not leak in.
        rows = [{"id": 1}, {"id": 2, "fetched_at": "not a timestamp"}]
        self.assertEqual(visible_at(rows, NOW), [])

    def test_published_time_is_not_what_gates_visibility(self):
        # Published days earlier, fetched later: invisible until fetched.
        rows = [{"id": 1, "created_at": "2026-09-01T00:00:00Z",
                 "fetched_at": "2026-09-14T21:00:00+00:00"}]
        self.assertEqual(
            visible_at(rows, datetime(2026, 9, 14, 20, tzinfo=timezone.utc)), [])


class Fetching(unittest.TestCase):
    def test_it_follows_pages_until_the_token_runs_out(self):
        pages = [
            {"news": [item(1, "one", "2026-09-14T13:00:00Z")], "next_page_token": "a"},
            {"news": [item(2, "two", "2026-09-14T13:05:00Z")], "next_page_token": "b"},
            {"news": [item(3, "three", "2026-09-14T13:10:00Z")]},
        ]
        seen = []

        def opener(url):
            seen.append(url)
            return pages[len(seen) - 1]

        got = fetch_news(["AAPL"], "2026-09-14", "2026-09-14", opener=opener)
        self.assertEqual([g["id"] for g in got], [1, 2, 3])
        self.assertEqual(len(seen), 3)
        self.assertTrue(seen[0].startswith(NEWS_URL))
        self.assertIn("page_token=a", seen[1])

    def test_no_symbols_makes_no_request(self):
        def opener(url):
            raise AssertionError("should not have been called")
        self.assertEqual(fetch_news([], "a", "b", opener=opener), [])

    def test_an_empty_feed_is_empty(self):
        self.assertEqual(
            fetch_news(["AAPL"], "a", "b", opener=lambda url: {"news": []}), [])


class Classification(unittest.TestCase):
    def test_events_carry_the_publishers_timestamp(self):
        events = to_events([item(1, "Apple launches foldable iPhone",
                                 "2026-09-12T14:00:00Z")])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].published_at.year, 2026)
        self.assertEqual(events[0].source, "benzinga")

    def test_an_unparseable_timestamp_becomes_none_not_an_error(self):
        events = to_events([item(1, "Something happened", "not a date")])
        self.assertIsNone(events[0].published_at)



RSS_XML = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>10-year Treasury yield hits highest level since 2007</title>
<link>https://example.test/yield</link>
<pubDate>Tue, 15 Sep 2026 13:00:00 GMT</pubDate></item>
<item><title>Fed holds rates steady</title>
<link>https://example.test/fed</link>
<pubDate>not a date</pubDate></item>
<item><title></title><link>https://example.test/blank</link></item>
</channel></rss>"""

ATOM_XML = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom style headline</title>
<link href="https://example.test/atom"/>
<updated>2026-09-15T13:00:00Z</updated></entry></feed>"""


class RssSources(unittest.TestCase):
    def test_an_rss_item_comes_back_shaped_like_an_alpaca_item(self):
        from event_aware_trader.news import fetch_rss
        got = fetch_rss("cnbc_top", "u", opener=lambda url: RSS_XML)
        self.assertEqual(len(got), 2)                 # the blank title is dropped
        first = got[0]
        # "summary" since 2026-10-04: the publisher's short summary, kept as
        # point-in-time research input (news.fetch_rss).
        self.assertEqual(set(first), {"id", "headline", "summary", "created_at",
                                      "symbols", "source", "url"})
        self.assertEqual(first["source"], "cnbc_top")
        self.assertEqual(first["symbols"], [])        # macro news names no ticker
        self.assertTrue(first["created_at"].startswith("2026-09-15"))

    def test_an_unparseable_date_is_none_rather_than_invented(self):
        from event_aware_trader.news import fetch_rss
        got = fetch_rss("cnbc_top", "u", opener=lambda url: RSS_XML)
        self.assertIsNone(got[1]["created_at"])

    def test_the_id_is_stable_across_refetches(self):
        from event_aware_trader.news import fetch_rss
        a = fetch_rss("x", "u", opener=lambda url: RSS_XML)
        b = fetch_rss("x", "u", opener=lambda url: RSS_XML)
        self.assertEqual([i["id"] for i in a], [i["id"] for i in b])

    def test_atom_feeds_parse_too(self):
        from event_aware_trader.news import fetch_rss
        got = fetch_rss("sec", "u", opener=lambda url: ATOM_XML)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["url"], "https://example.test/atom")

    def test_a_dead_feed_is_skipped_not_fatal(self):
        from event_aware_trader.news import fetch_all_rss

        def opener(url):
            if "dead" in url:
                raise OSError("getaddrinfo failed")
            return RSS_XML

        got = fetch_all_rss(sources=(("dead", "http://dead"),
                                     ("alive", "http://alive")), opener=opener)
        self.assertEqual(len(got), 2)                 # only the live feed's items
        self.assertTrue(all(i["source"] == "alive" for i in got))

    def test_malformed_xml_is_skipped_not_fatal(self):
        from event_aware_trader.news import fetch_rss
        self.assertEqual(fetch_rss("x", "u", opener=lambda url: b"<not xml"), [])

    def test_rss_and_alpaca_rows_land_in_one_file_with_one_schema(self):
        from event_aware_trader.news import fetch_rss
        with TemporaryDirectory() as tmp:
            rss = fetch_rss("cnbc_top", "u", opener=lambda url: RSS_XML)
            alpaca = [item(1, "Apple launches foldable iPhone", "2026-09-12T14:00:00Z")]
            record(rss + alpaca, Path(tmp), NOW)
            rows = load_day(NOW.date(), Path(tmp))
            self.assertEqual(len(rows), 3)
            for r in rows:
                self.assertIn("fetched_at", r)
                self.assertIn("category", r)
            self.assertEqual({r["source"] for r in rows}, {"cnbc_top", "benzinga"})

if __name__ == "__main__":
    unittest.main()
