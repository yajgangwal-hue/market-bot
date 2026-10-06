"""A close made at the broker is recognized however long the trade was held.

Until 2026-10-05 the bot read one page of fills - the account's last 100.
A position held while more than 100 fills happened (cash parking, partial
fills, other entries) had its entry fall off that page, and its close at the
broker - the resting take profit filling, or the stop - was logged as
`external_exit_unrecoverable`: a real gain or loss the reports never
recognized. The bot now reads further back when, and only when, it needs to,
and an error while doing so leaves the cycle exactly as it was before.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader import live_model
from event_aware_trader.autotrade import AutoTradeConfig, _learn_from_external_exits
from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig, BrokerError


def activity(n, symbol="SGOV", side="buy", qty="1", price="100", t=None):
    return {"id": "a{0:05d}".format(n), "symbol": symbol, "side": side, "qty": qty,
            "price": price, "transaction_time": t or "2026-10-{0:02d}T15:00:00.123Z".format(
                20 - n // 100), "order_id": "o{0}".format(n)}


class PagingBroker(AlpacaPaperBroker):
    """The real broker class with its HTTP request replaced by a fixed feed."""

    def __init__(self, feed):
        super().__init__(BrokerConfig(key_id="test", secret_key="test",
                                      allow_order_submission=False))
        self.feed = feed                 # newest first, as Alpaca returns them
        self.paths = []

    def _request(self, method, path, payload=None):
        self.paths.append(path)
        query = dict(part.split("=", 1) for part in path.split("?", 1)[1].split("&"))
        size = int(query["page_size"])
        start = 0
        if "page_token" in query:
            start = next(i for i, a in enumerate(self.feed) if a["id"] == query["page_token"]) + 1
        return self.feed[start:start + size]


class FillActivitiesBackTo(unittest.TestCase):
    def test_follows_page_tokens_until_older_than_the_cutoff(self):
        feed = [activity(n) for n in range(450)]          # 2026-10-20 back to 2026-10-16
        broker = PagingBroker(feed)
        rows = broker.fill_activities_back_to("2026-10-18T00:00:00")
        # Pages end on 10-20, 10-19, 10-18 15:00 (still after the cutoff) and
        # 10-17 (before it): the fourth page is the one that crosses.
        self.assertEqual(len(rows), 400)
        self.assertEqual(rows[0]["id"], "a00000")
        self.assertIn("page_token=a00099", broker.paths[1])
        self.assertIn("page_token=a00299", broker.paths[3])
        self.assertEqual(len(broker.paths), 4)

    def test_stops_at_a_short_page(self):
        broker = PagingBroker([activity(n) for n in range(130)])
        rows = broker.fill_activities_back_to("2000-01-01T00:00:00")
        self.assertEqual(len(rows), 130)
        self.assertEqual(len(broker.paths), 2)

    def test_stops_at_max_pages(self):
        broker = PagingBroker([activity(n, t="2026-10-20T15:00:00Z") for n in range(1000)])
        rows = broker.fill_activities_back_to("2000-01-01T00:00:00", max_pages=3)
        self.assertEqual((len(rows), len(broker.paths)), (300, 3))

    def test_the_one_page_read_is_unchanged(self):
        broker = PagingBroker([activity(n) for n in range(250)])
        rows = broker.fill_activities(page_size=100)
        self.assertEqual(len(rows), 100)
        self.assertEqual(broker.paths, ["/v2/account/activities/FILL?page_size=100"])
        self.assertEqual(rows[0]["id"], "a00000")


FEATURES = {k: 0.5 for k in live_model.LIVE_FEATURES}


class Feed:
    """A test double with the one-page read and, optionally, the pager."""

    def __init__(self, fills, held=(), pager_fills=None, pager_error=None):
        self.fills, self.held = fills, list(held)
        self.pager_fills, self.pager_error = pager_fills, pager_error
        self.paged = []

    def positions(self):
        return [{"symbol": s} for s in self.held]

    def fill_activities(self, page_size=100):
        return self.fills[:page_size]

    def back_to(self, oldest):
        self.paged.append(oldest)
        if self.pager_error:
            raise self.pager_error
        return self.pager_fills


def schw_trip():
    entry = {"id": "e1", "symbol": "SCHW", "side": "buy", "qty": "100", "price": "98.36",
             "transaction_time": "2026-10-01T19:45:43Z"}
    close = {"id": "x1", "symbol": "SCHW", "side": "sell", "qty": "100", "price": "107.78",
             "transaction_time": "2026-10-27T15:31:00Z"}
    noise = [{"id": "n{0}".format(i), "symbol": "SGOV", "side": "buy", "qty": "1",
              "price": "100.5", "transaction_time": "2026-10-2{0}T15:00:00Z".format(i % 7)}
             for i in range(120)]
    newest_first = [close] + noise + [entry]
    return newest_first


class TakeProfitFilledLongAfterTheEntry(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._real = live_model.TRAINING_PATH
        live_model.TRAINING_PATH = Path(self._tmp.name) / "examples.jsonl"
        self.config = AutoTradeConfig(dry_run=True,
                                      audit_log=Path(self._tmp.name) / "audit.jsonl",
                                      state_file=Path(self._tmp.name) / "state.json")

    def tearDown(self):
        live_model.TRAINING_PATH = self._real
        self._tmp.cleanup()

    def state(self):
        return {"open_features": {"SCHW": dict(FEATURES)},
                "stops": {"SCHW": {"initial": 92.84, "current": 92.84, "take_profit": 107.78,
                                   "opened_at_ts": "2026-10-01T19:45:43+00:00"}}}

    def events(self, actions):
        return [a.get("event") for a in actions]

    def test_recognized_when_the_broker_can_page(self):
        trip = schw_trip()
        feed = Feed(trip, pager_fills=trip)
        feed.fill_activities_back_to = feed.back_to
        state, actions = self.state(), []
        _learn_from_external_exits(self.config, feed, state, actions)
        self.assertIn("learned_from_external_exit", self.events(actions))
        booked = next(a for a in actions if a.get("event") == "learned_from_external_exit")
        self.assertAlmostEqual(booked["detail"]["realized_pnl"], (107.78 - 98.36) * 100, places=2)
        self.assertEqual(feed.paged, ["2026-09-29T19:45:43"])   # two days before the entry
        self.assertNotIn("SCHW", state["stops"])

    def test_without_a_pager_it_behaves_as_before(self):
        state, actions = self.state(), []
        _learn_from_external_exits(self.config, Feed(schw_trip()), state, actions)
        self.assertIn("external_exit_unrecoverable", self.events(actions))

    def test_a_paging_error_keeps_the_page_and_the_cycle(self):
        feed = Feed(schw_trip(), pager_error=BrokerError("HTTP 500"))
        feed.fill_activities_back_to = feed.back_to
        state, actions = self.state(), []
        _learn_from_external_exits(self.config, feed, state, actions)
        names = self.events(actions)
        self.assertIn("external_exit_fill_paging_failed", names)
        self.assertIn("external_exit_unrecoverable", names)

    def test_no_paging_when_the_first_page_already_has_the_trip(self):
        recent = [{"id": "x", "symbol": "SCHW", "side": "sell", "qty": "100", "price": "107.78",
                   "transaction_time": "2026-10-27T15:31:00Z"},
                  {"id": "e", "symbol": "SCHW", "side": "buy", "qty": "100", "price": "98.36",
                   "transaction_time": "2026-10-01T19:45:43Z"}]
        feed = Feed(recent, pager_fills=[])
        feed.fill_activities_back_to = feed.back_to
        actions = []
        _learn_from_external_exits(self.config, feed, self.state(), actions)
        self.assertEqual(feed.paged, [])
        self.assertIn("learned_from_external_exit", self.events(actions))


if __name__ == "__main__":
    unittest.main()
