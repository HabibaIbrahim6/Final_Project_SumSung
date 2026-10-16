import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from models import AdminUser, Coordinator, Donor, NGOUser
from session import sync_tracking_data
from services.allocation_service import AllocationService
from services.distribution import CONFIRMED, DELIVERED, CANCELLED
from services.donation_service import DonationService
from services.tracking_service import TrackingService


def make_user(user_type, user_id, **extra):
    return user_type(
        user_id,
        "Test User",
        "test@example.com",
        "01012345678",
        "Passw0rd1",
        **extra,
    )


class TestTrackingIntegration(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.donations = DonationService(root / "donations.csv")
        self.allocation = AllocationService(
            self.donations,
            root / "ngos.json",
        )
        self.tracking = TrackingService(
            root / "distributions.csv",
            root / "distribution_log.csv",
            auto_save=True,
        )
        self.donor = make_user(Donor, "USR-0002")
        self.coordinator = make_user(Coordinator, "USR-0003")
        self.admin = make_user(AdminUser, "USR-0001")
        tomorrow = date.today() + timedelta(days=1)
        self.donation = self.donations.create(
            self.donor,
            "Bread",
            "Bakery",
            2,
            "kg",
            tomorrow,
            "Cairo",
            "12 Tahrir Street",
            "09:00",
            "17:00",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _approve_donation(self):
        self.allocation.propose(self.coordinator, self.donation.donation_id)
        self.allocation.approve(self.admin, self.donation.donation_id)
        sync_tracking_data(self.tracking, self.donations, self.allocation)
        return self.tracking.list_distributions()[-1]

    def test_approved_kg_allocation_is_tracked_and_synced(self):
        record = self._approve_donation()
        self.assertEqual(record.status, CONFIRMED)
        self.assertEqual(self.tracking.history_entries(), [])
        self.assertEqual(len(self.tracking.list_distributions()), 1)
        sync_tracking_data(self.tracking, self.donations, self.allocation)
        self.assertEqual(len(self.tracking.list_distributions()), 1)

        self.tracking.start_transit(record.distribution_id)
        self.tracking.mark_delivered(record.distribution_id)
        ngo = make_user(NGOUser, "USR-0004", ngo_id=record.ngo_id)
        self.allocation.mark_delivered(ngo, self.donation.donation_id)
        sync_tracking_data(self.tracking, self.donations, self.allocation)
        self.assertEqual(self.donations.get(self.donation.donation_id).status, "Delivered")
        self.assertEqual(self.tracking.get(record.distribution_id).status, DELIVERED)

    def test_cancellation_releases_allocation_and_capacity(self):
        record = self._approve_donation()
        allocated_capacity = self.allocation.ngo_by_id(record.ngo_id)["remaining_capacity"]["kg"]
        self.tracking.cancel(record.distribution_id, "Pickup unavailable")
        self.allocation.release_assignment(self.admin, self.donation.donation_id)
        self.assertEqual(self.donations.get(self.donation.donation_id).status, "Pending")
        self.assertEqual(self.tracking.get(record.distribution_id).status, CANCELLED)
        self.assertEqual(
            self.allocation.ngo_by_id(record.ngo_id)["remaining_capacity"]["kg"],
            allocated_capacity + self.donation.quantity,
        )
        self.assertEqual(self.allocation.history.size(), 0)


if __name__ == "__main__":
    unittest.main()
