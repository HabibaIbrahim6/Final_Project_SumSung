import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta

from allocation_service import AllocationService
from donation_service import DonationService
from models import AdminUser, Donor, NGOUser
from user_service import UserService
from validators import InvalidStateError, ValidationError


def make_user(cls, user_id, **extra):
    return cls(user_id, "NGO Representative", "rep@example.com",
               "01012345678", "Passw0rd1", **extra)


class TestNGOIntegration(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.donations = DonationService(os.path.join(self.directory, "donations.csv"))
        self.allocation = AllocationService(
            self.donations, os.path.join(self.directory, "ngos.json")
        )
        self.donor = make_user(Donor, "USR-0002")
        self.ngo_user = make_user(NGOUser, "USR-0003", ngo_id="4")
        self.admin = make_user(AdminUser, "USR-0001")
        self.donation = self.donations.create(
            self.donor,
            "Bread",
            "Bakery",
            20,
            "items",
            date.today() + timedelta(days=1),
            "Cairo",
            "12 Tahrir Street",
            "09:00",
            "17:00",
        )

    def tearDown(self):
        shutil.rmtree(self.directory)

    def test_ngo_registration_is_linked_and_persisted(self):
        service = UserService(os.path.join(self.directory, "users.json"))
        registered = service.register(
            "NGO Representative",
            "rep@example.com",
            "Passw0rd1",
            "01012345678",
            role="ngo",
            ngo_id=4,
        )
        self.assertEqual(registered.ngo_id, "4")
        self.assertEqual(service.get(registered.user_id).ngo_id, "4")

    def test_ngo_sees_eligible_donations_and_can_mark_its_assignment_delivered(self):
        eligible = self.allocation.eligible_donations(self.ngo_user)
        self.assertEqual([item.donation_id for item in eligible], [self.donation.donation_id])

        self.allocation.confirm(self.donation.donation_id, 4)
        delivered = self.allocation.mark_delivered(self.ngo_user, self.donation.donation_id)
        self.assertEqual(delivered.status, "Delivered")

    def test_ngo_cannot_update_another_ngos_donation(self):
        other_ngo = make_user(NGOUser, "USR-0004", ngo_id="1")
        self.allocation.confirm(self.donation.donation_id, 4)
        with self.assertRaises(InvalidStateError):
            self.allocation.mark_delivered(other_ngo, self.donation.donation_id)

    def test_unlinked_ngo_account_is_blocked_until_admin_link(self):
        unlinked = make_user(NGOUser, "USR-0005")
        with self.assertRaises(InvalidStateError):
            self.allocation.eligible_donations(unlinked)

    def test_ngo_profile_changes_feed_the_eligibility_matcher(self):
        self.allocation.update_ngo_profile(
            self.ngo_user,
            "Bread for All",
            "Cairo",
            10,
            ["Cooked Meals"],
            {"kg": 10, "portions": 10, "liters": 10, "boxes": 10, "items": 10},
        )
        self.assertEqual(self.allocation.eligible_donations(self.ngo_user), [])

    def test_admin_can_update_profiles_used_by_allocation(self):
        self.allocation.update_ngo_profile(
            self.admin,
            "Bread for All",
            "Cairo",
            5,
            ["Bakery"],
            {"kg": 60, "portions": 0, "liters": 0, "boxes": 40, "items": 200},
            ngo_id=4,
        )
        self.assertEqual(self.allocation.ngo_by_id("4")["pickup_time_minutes"], 5)

    def test_invalid_pickup_preparation_time_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.allocation.update_ngo_profile(
                self.ngo_user,
                "Bread for All",
                "Cairo",
                2.5,
                ["Bakery"],
                {"items": 10},
            )


if __name__ == "__main__":
    unittest.main()
