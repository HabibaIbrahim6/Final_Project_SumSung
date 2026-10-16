"""Build analytics tables from the application's current services."""

import pandas as pd

DONATION_COLUMNS = [
    "donation_id",
    "donor_id",
    "donor_name",
    "donor_type",
    "food_type",
    "quantity_kg",
    "city",
    "created_at",
    "expiry_date",
    "status",
]
NGO_COLUMNS = [
    "ngo_id",
    "ngo_name",
    "city",
    "area",
    "contact_person",
    "phone",
    "capacity_kg_per_day",
    "registration_date",
    "status",
]
DISTRIBUTION_COLUMNS = [
    "distribution_id",
    "donation_id",
    "ngo_id",
    "allocated_quantity_kg",
    "delivered_quantity_kg",
    "allocated_at",
    "delivered_at",
    "status",
]

_STATUS_LABELS = {
    "proposed": "Allocated",
    "confirmed": "Allocated",
    "in_transit": "In Transit",
    "delivered": "Delivered",
    "failed": "Failed",
    "cancelled": "Cancelled",
}


def load_live_data(donations, users, allocation, tracking):
    user_records = users.records
    donation_rows = []
    for donation in donations.all_donations():
        if donation.unit != "kg":
            continue
        donor = user_records.get(donation.donor_id, {})
        donation_rows.append(
            {
                "donation_id": donation.donation_id,
                "donor_id": donation.donor_id,
                "donor_name": donor.get("organization") or donor.get("full_name", "Unknown"),
                "donor_type": donor.get("donor_type", "Other"),
                "food_type": donation.category,
                "quantity_kg": donation.quantity,
                "city": donation.city,
                "created_at": donation.created_at,
                "expiry_date": donation.expiry_date,
                "status": donation.status,
            }
        )

    ngo_rows = [
        {
            "ngo_id": str(ngo["id"]),
            "ngo_name": ngo["name"],
            "city": ngo["location"],
            "area": ngo["location"],
            "contact_person": "",
            "phone": "",
            "capacity_kg_per_day": ngo["remaining_capacity"].get("kg", 0),
            "registration_date": "",
            "status": "Active",
        }
        for ngo in allocation.ngos
    ]

    distribution_rows = [
        {
            "distribution_id": record.distribution_id,
            "donation_id": record.donation_id,
            "ngo_id": record.ngo_id,
            "allocated_quantity_kg": record.allocated_quantity_kg,
            "delivered_quantity_kg": record.delivered_quantity_kg,
            "allocated_at": record.allocated_at,
            "delivered_at": record.delivered_at or "",
            "status": _STATUS_LABELS[record.status],
        }
        for record in tracking.list_distributions()
    ]

    donation_frame = pd.DataFrame(donation_rows, columns=DONATION_COLUMNS)
    ngo_frame = pd.DataFrame(ngo_rows, columns=NGO_COLUMNS)
    distribution_frame = pd.DataFrame(distribution_rows, columns=DISTRIBUTION_COLUMNS)
    for column in ("created_at", "expiry_date"):
        donation_frame[column] = pd.to_datetime(donation_frame[column], errors="coerce")
    for column in ("allocated_at", "delivered_at"):
        distribution_frame[column] = pd.to_datetime(distribution_frame[column], errors="coerce")
    return {
        "donations": donation_frame,
        "ngos": ngo_frame,
        "distributions": distribution_frame,
    }
