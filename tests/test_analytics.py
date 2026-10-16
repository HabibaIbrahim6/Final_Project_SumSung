import unittest
from datetime import date
from types import SimpleNamespace

from analytics.access import scope_data
from analytics.data_loader import load_live_data
from analytics.metrics import (
    donor_impact_report,
    ngo_performance_report,
    total_delivered_kg,
)
from services.distribution import DELIVERED, Distribution


class FakeDonations:
    def __init__(self, records):
        self._records = records

    def all_donations(self):
        return self._records


class FakeTracking:
    def __init__(self, records):
        self._records = records

    def list_distributions(self):
        return self._records


class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.donation = SimpleNamespace(
            donation_id="DON-0001",
            donor_id="USR-0001",
            food_name="Bread",
            donor_name="Test donor",
            donor_type="Bakery",
            category="Bakery",
            quantity=4.0,
            unit="kg",
            city="Cairo",
            created_at="2026-10-01 09:00:00",
            expiry_date=date(2026, 10, 2),
            status="Delivered",
        )
        self.non_kg_donation = SimpleNamespace(
            donation_id="DON-0002",
            donor_id="USR-0001",
            category="Cooked Meals",
            quantity=20.0,
            unit="portions",
        )
        distribution = Distribution(
            "DIS-0001",
            "DON-0001",
            "4",
            4,
            4,
            allocated_at="2026-10-01 09:30:00",
            delivered_at="2026-10-01 10:00:00",
            status=DELIVERED,
        )
        self.data = load_live_data(
            FakeDonations([self.donation, self.non_kg_donation]),
            SimpleNamespace(
                records={"USR-0001": {"full_name": "Test donor", "donor_type": "Bakery"}}
            ),
            SimpleNamespace(
                ngos=[
                    {
                        "id": 4,
                        "name": "Bread for All",
                        "location": "Cairo",
                        "remaining_capacity": {"kg": 6},
                    }
                ]
            ),
            FakeTracking([distribution]),
        )

    def test_live_adapter_only_includes_kg_donations(self):
        self.assertEqual(self.data["donations"]["donation_id"].tolist(), ["DON-0001"])
        self.assertEqual(self.data["donations"].iloc[0]["quantity_kg"], 4)
        self.assertEqual(self.data["distributions"].iloc[0]["status"], "Delivered")

    def test_reports_and_role_scope_use_live_records(self):
        donations, distributions = scope_data(
            self.data["donations"],
            self.data["distributions"],
            "donor",
            "USR-0001",
        )
        donor_report = donor_impact_report(donations, distributions)
        ngo_report = ngo_performance_report(
            donations,
            distributions,
            self.data["ngos"],
        )
        self.assertEqual(donor_report.iloc[0]["delivered_kg"], 4)
        self.assertEqual(ngo_report.iloc[0]["success_rate_pct"], 100)
        self.assertEqual(total_delivered_kg(distributions), 4)


if __name__ == "__main__":
    unittest.main()
