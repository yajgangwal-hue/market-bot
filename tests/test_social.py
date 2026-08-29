import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.social import Entity, SocialPost, evaluate_post, source_from_mapping


class SocialMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)
        self.entities = [Entity("DELL", ("dell", "dell technologies"), "Dell Technologies")]

    def test_exact_verified_fresh_post_with_entity_is_review_required(self):
        post = SocialPost(
            post_id="post-1",
            platform="bluesky",
            source_name="verified source",
            author="official.example",
            author_id="did:plc:immutable",
            text="Dell Technologies was mentioned in today's statement.",
            published_at=self.now - timedelta(minutes=2),
            url="https://example.test/post-1",
            identity_verified=True,
        )
        alert = evaluate_post(post, self.entities, now=self.now)
        self.assertEqual(alert.status, "REVIEW_REQUIRED")
        self.assertEqual(alert.tickers, ("DELL",))
        self.assertTrue(alert.requires_human_stance)
        self.assertTrue(alert.paper_only)

    def test_unverified_source_cannot_clear_the_gate(self):
        post = SocialPost(
            post_id="post-2",
            platform="x",
            source_name="lookalike",
            author="lookalike",
            author_id="unexpected",
            text="Dell will soar",
            published_at=self.now - timedelta(minutes=1),
            url="https://example.test/post-2",
            identity_verified=False,
        )
        alert = evaluate_post(post, self.entities, now=self.now)
        self.assertEqual(alert.status, "HOLD")
        self.assertLess(alert.trust_score, 90)

    def test_rumor_language_blocks_an_otherwise_verified_post(self):
        post = SocialPost(
            post_id="post-3",
            platform="rss",
            source_name="official feed",
            author="official feed",
            author_id="official.example",
            text="Rumor: Dell may announce something",
            published_at=self.now - timedelta(minutes=1),
            url="https://official.example/post-3",
            identity_verified=True,
        )
        alert = evaluate_post(post, self.entities, now=self.now)
        self.assertEqual(alert.status, "HOLD")
        self.assertIn("Rumor-language filter triggered", alert.reasons)

    def test_enabled_bluesky_source_requires_immutable_did(self):
        with self.assertRaises(ValueError):
            source_from_mapping(
                {
                    "name": "bad source",
                    "platform": "bluesky",
                    "official": True,
                    "enabled": True,
                    "actor": "official.example",
                }
            )


if __name__ == "__main__":
    unittest.main()
