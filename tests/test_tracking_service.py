import csv
import tempfile
import unittest
from pathlib import Path

from services.distribution import (
    CONFIRMED,
    DELIVERED,
    IN_TRANSIT,
    PROPOSED,
    CapacityExceededError,
    DistributionError,
    InvalidStatusTransition,
)
from services.tracking_service import TrackingService


class TestTrackingService(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.service = TrackingService(
            root / "distributions.csv",
            root / "distribution_log.csv",
            auto_save=True,
        )
        self.service.register_donation("DON-0001", 10)
        self.service.register_ngo("4", 8)

    def tearDown(self):
        self.directory.cleanup()

    def test_lifecycle_and_partial_delivery_release_unused_capacity(self):
        record = self.service.create_distribution("DON-0001", "4", 6)
        self.assertEqual(record.status, PROPOSED)
        self.service.confirm(record.distribution_id)
        self.assertEqual(self.service.donation_remaining_kg("DON-0001"), 4)
        self.assertEqual(self.service.ngo_remaining_capacity_kg("4"), 2)

        self.service.start_transit(record.distribution_id)
        delivered = self.service.mark_delivered(record.distribution_id, 5)
        self.assertEqual(delivered.status, DELIVERED)
        self.assertEqual(self.service.donation_remaining_kg("DON-0001"), 5)
        self.assertEqual(self.service.ngo_remaining_capacity_kg("4"), 3)

    def test_capacity_and_transition_rules_are_enforced(self):
        with self.assertRaises(CapacityExceededError):
            self.service.create_distribution("DON-0001", "4", 9)

        record = self.service.create_distribution("DON-0001", "4", 2)
        with self.assertRaises(InvalidStatusTransition):
            self.service.start_transit(record.distribution_id)
        self.service.confirm(record.distribution_id)
        self.assertEqual(record.status, CONFIRMED)

    def test_undo_restores_the_previous_record_snapshot(self):
        record = self.service.create_distribution("DON-0001", "4", 3)
        self.service.confirm(record.distribution_id)
        self.service.undo_last()
        self.assertEqual(self.service.get(record.distribution_id).status, PROPOSED)
        self.service.undo_last()
        self.assertEqual(self.service.list_distributions(), [])

    def test_csv_round_trip_keeps_state_and_status_history(self):
        record = self.service.create_distribution("DON-0001", "4", 4)
        self.service.confirm(record.distribution_id)
        self.service.start_transit(record.distribution_id)
        self.service.mark_delivered(record.distribution_id, 4)

        loaded = TrackingService(
            self.service.distributions_path,
            self.service.log_path,
            auto_save=True,
        )
        restored = loaded.get(record.distribution_id)
        self.assertEqual(restored.status, DELIVERED)
        self.assertEqual(restored.delivered_quantity_kg, 4)
        self.assertEqual(len(restored.status_history), 4)

        with self.service.distributions_path.open(newline="", encoding="utf-8") as file:
            self.assertEqual(len(list(csv.DictReader(file))), 1)

    def test_reason_is_required_for_terminal_failure(self):
        record = self.service.create_distribution("DON-0001", "4", 2)
        self.service.confirm(record.distribution_id)
        self.service.start_transit(record.distribution_id)
        with self.assertRaises(DistributionError):
            self.service.fail(record.distribution_id, "")


if __name__ == "__main__":
    unittest.main()
