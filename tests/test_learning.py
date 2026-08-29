import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.learning import example_from_mapping, forecast_scenario, train_model


def example(index, trust_score, outcome_return_bps):
    return example_from_mapping(
        {
            "example_id": "example-{0}".format(index),
            "published_at": (datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index)).isoformat(),
            "platform": "rss" if index % 2 else "bluesky",
            "trust_score": trust_score,
            "age_minutes": 1 if trust_score >= 90 else 40,
            "text_length": 200,
            "entity_count": 1,
            "direction": "up",
            "claim_type": "company",
            "outcome_return_bps": outcome_return_bps,
            "friction_bps": 6,
            "horizon_minutes": 60,
        }
    )


class LearningTests(unittest.TestCase):
    def test_label_is_cost_adjusted_and_directional(self):
        up = example_from_mapping(
            {
                "example_id": "up",
                "published_at": "2026-01-01T00:00:00+00:00",
                "platform": "rss",
                "trust_score": 100,
                "age_minutes": 1,
                "text_length": 100,
                "entity_count": 1,
                "direction": "up",
                "claim_type": "company",
                "outcome_return_bps": 6,
                "friction_bps": 6,
                "horizon_minutes": 60,
            }
        )
        down = example_from_mapping(
            {
                "example_id": "down",
                "published_at": "2026-01-01T01:00:00+00:00",
                "platform": "rss",
                "trust_score": 100,
                "age_minutes": 1,
                "text_length": 100,
                "entity_count": 1,
                "direction": "down",
                "claim_type": "company",
                "outcome_return_bps": -7,
                "friction_bps": 6,
                "horizon_minutes": 60,
            }
        )
        self.assertEqual(up.label, 0)
        self.assertEqual(down.label, 1)

    def test_small_dataset_remains_unproven_and_forecast_holds(self):
        examples = [example(index, 100 if index % 2 else 20, 20 if index % 2 else -20) for index in range(40)]
        model = train_model(examples, min_examples=20, epochs=250)
        self.assertEqual(model.status, "UNPROVEN")
        self.assertEqual(model.report["out_of_sample_count"], 12)
        result = forecast_scenario(
            model,
            {
                "platform": "rss",
                "trust_score": 100,
                "age_minutes": 1,
                "text_length": 200,
                "entity_count": 1,
                "direction": "up",
                "claim_type": "company",
            },
        )
        self.assertEqual(result["decision"], "HOLD_FOR_HUMAN_REVIEW")
        self.assertGreaterEqual(result["historical_alignment_probability"], 0.0)
        self.assertLessEqual(result["historical_alignment_probability"], 1.0)

    def test_training_requires_enough_labels(self):
        with self.assertRaises(ValueError):
            train_model([example(index, 100, 20) for index in range(10)])


if __name__ == "__main__":
    unittest.main()
