import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta

from allocation_service import AllocationService
from donation_service import DonationService
from models import AdminUser, Coordinator, Donor
from validators import AuthorizationError, InvalidStateError


def make_user(cls, user_id, **extra):
    return cls(user_id, "Test User", "test@example.com", "01012345678", "Passw0rd1", **extra)


class TestAllocationService(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.donations = DonationService(os.path.join(self.dir, "donations.csv"))
        self.allocation = AllocationService(self.donations, os.path.join(self.dir, "ngos.json"))
        self.donor = make_user(Donor, "USR-0002")
        self.coordinator = make_user(Coordinator, "USR-0003")
        self.admin = make_user(AdminUser, "USR-0001")
        tomorrow = date.today() + timedelta(days=1)
        later = date.today() + timedelta(days=3)
        self.bakery = self.donations.create(self.donor, "Bread", "Bakery", 100, "items", tomorrow, "Cairo",
                                            "12 Tahrir Street", "09:00", "17:00")
        self.meals = self.donations.create(self.donor, "Rice meals", "Cooked Meals", 40, "portions", later,
                                           "Giza", "5 Pyramids Road", "09:00", "17:00")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_queue_is_most_urgent_first(self):
        refs = [d["ref"] for d in self.allocation.get_pending_queue()]
        self.assertEqual(refs, [self.bakery.donation_id, self.meals.donation_id])

    def test_recommendation_has_reasons(self):
        rec = self.allocation.recommend(self.bakery.donation_id)
        self.assertEqual(rec["ngo"]["name"], "Bread for All")
        self.assertTrue(rec["reasons"])

    def test_full_approval_flow(self):
        ref = self.bakery.donation_id
        self.allocation.propose(self.coordinator, ref)
        self.assertEqual(len(self.allocation.open_proposals()), 1)
        self.allocation.approve(self.admin, ref)
        donation = self.donations.get(ref)
        self.assertEqual(donation.status, "Allocated")
        self.assertEqual(donation.ngo_id, "4")
        self.assertEqual(self.allocation.ngo_by_id(4)["remaining_capacity"]["items"], 100)
        self.assertEqual(len(self.allocation.get_pending_queue()), 1)

    def test_undo(self):
        ref = self.bakery.donation_id
        self.allocation.propose(self.coordinator, ref)
        self.allocation.approve(self.admin, ref)
        self.allocation.undo_last(self.admin)
        donation = self.donations.get(ref)
        self.assertEqual(donation.status, "Pending")
        self.assertEqual(donation.ngo_id, "")
        self.assertEqual(self.allocation.ngo_by_id(4)["remaining_capacity"]["items"], 200)

    def test_undo_without_history(self):
        with self.assertRaises(InvalidStateError):
            self.allocation.undo_last(self.admin)

    def test_reject_keeps_donation_pending(self):
        ref = self.bakery.donation_id
        self.allocation.propose(self.coordinator, ref)
        self.allocation.reject(self.admin, ref)
        self.assertEqual(self.donations.get(ref).status, "Pending")
        self.assertEqual(self.allocation.open_proposals(), [])

    def test_permissions(self):
        ref = self.bakery.donation_id
        with self.assertRaises(AuthorizationError):
            self.allocation.propose(self.donor, ref)
        self.allocation.propose(self.coordinator, ref)
        with self.assertRaises(AuthorizationError):
            self.allocation.approve(self.coordinator, ref)

    def test_cancelled_donation_cannot_be_proposed(self):
        self.donations.cancel(self.donor, self.bakery.donation_id, "Donated elsewhere")
        with self.assertRaises(InvalidStateError):
            self.allocation.propose(self.coordinator, self.bakery.donation_id)

    def test_proposal_becomes_outdated_when_cancelled(self):
        ref = self.bakery.donation_id
        self.allocation.propose(self.coordinator, ref)
        self.donations.cancel(self.donor, ref, "Donated elsewhere")
        self.assertEqual(self.allocation.open_proposals(), [])

    def test_allocation_survives_restart(self):
        ref = self.bakery.donation_id
        self.allocation.propose(self.coordinator, ref)
        self.allocation.approve(self.admin, ref)
        donations = DonationService(os.path.join(self.dir, "donations.csv"))
        allocation = AllocationService(donations, os.path.join(self.dir, "ngos.json"))
        self.assertEqual(donations.get(ref).ngo_id, "4")
        self.assertEqual(allocation.ngo_by_id(4)["remaining_capacity"]["items"], 100)

    def test_compare_with_baseline(self):
        result = self.allocation.compare_with_baseline()
        self.assertLessEqual(result["greedy"]["avg_minutes"], result["baseline"]["avg_minutes"])


if __name__ == "__main__":
    unittest.main()
