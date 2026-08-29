import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.events import active_event_impact, classify_headline, in_event_blackout
from event_aware_trader.types import Event


class EventTests(unittest.TestCase):
    def test_classifier_is_conservative_but_finds_hawkish_inflation_terms(self):
        event = classify_headline("CPI comes in hotter as inflation remains sticky")
        self.assertEqual(event.category, "inflation")
        self.assertEqual(event.stance, "hawkish")
        self.assertLessEqual(event.confidence, 0.55)

    def test_impact_requires_information_to_be_public(self):
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        future = Event("future inflation", "inflation", "hawkish", 1.0, published_at=now + timedelta(days=1))
        past = Event("past inflation", "inflation", "hawkish", 1.0, published_at=now - timedelta(hours=2))
        future_score, _ = active_event_impact("QQQ", [future], now)
        past_score, _ = active_event_impact("QQQ", [past], now)
        self.assertEqual(future_score, 0.0)
        self.assertLess(past_score, 0.0)

    def test_scheduled_event_creates_blackout(self):
        now = datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc)
        event = Event("scheduled decision", "central_bank", scheduled_at=now + timedelta(minutes=30))
        self.assertEqual(in_event_blackout(now, [event]).title, "scheduled decision")


if __name__ == "__main__":
    unittest.main()
