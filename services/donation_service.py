import csv
import os

import config
from models import Donation, check_permission, donation_from_row, now_text
from validators import (AuthorizationError, DuplicateError, InvalidStateError, NotFoundError,
                        clean_text, validate_choice, validate_donation_id, validate_expiry_date,
                        validate_pickup_window, validate_quantity)


class DonationService:
    def __init__(self, path=None):
        self.path = path or config.donations_file
        self.records = {}
        self.by_donor = {}
        self.ids = set()
        self.load()
        self.expire_overdue()

    def load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                try:
                    donation = donation_from_row(row)
                except (KeyError, ValueError, TypeError):
                    continue
                if donation.donation_id not in self.ids:
                    self.add_record(donation)

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=config.donation_fields, lineterminator="\n")
            writer.writeheader()
            for donation in self.records.values():
                writer.writerow(donation.to_row())

    def add_record(self, donation):
        self.records[donation.donation_id] = donation
        self.ids.add(donation.donation_id)
        self.by_donor.setdefault(donation.donor_id, []).append(donation.donation_id)

    def new_id(self):
        number = len(self.ids) + 1
        while f"DON-{number:04d}" in self.ids:
            number += 1
        return f"DON-{number:04d}"

    def check_fields(self, food_name, category, quantity, unit, expiry_date, city,
                     pickup_location, pickup_from, pickup_until, notes):
        food_name = clean_text(food_name, "Food name", 2, 80)
        category = validate_choice(category, config.food_categories, "Food category")
        quantity = validate_quantity(quantity)
        unit = validate_choice(unit, config.units, "Unit")
        expiry_date = validate_expiry_date(expiry_date)
        city = validate_choice(city, config.cities, "City")
        pickup_location = clean_text(pickup_location, "Pickup location", 5, 150)
        pickup_from, pickup_until = validate_pickup_window(pickup_from, pickup_until)
        notes = " ".join(str(notes or "").split())[:300]
        return {"food_name": food_name, "category": category, "quantity": quantity,
                "unit": unit, "expiry_date": expiry_date, "city": city,
                "pickup_location": pickup_location,
                "pickup_from": pickup_from, "pickup_until": pickup_until, "notes": notes}

    def check_duplicate(self, donor_id, fields, ignore_id=None):
        for donation_id in self.by_donor.get(donor_id, []):
            other = self.records[donation_id]
            if (donation_id != ignore_id and other.is_pending()
                    and other.food_name.lower() == fields["food_name"].lower()
                    and other.expiry_date == fields["expiry_date"]
                    and other.quantity == fields["quantity"]):
                raise DuplicateError(f"You already have an identical pending donation ({donation_id}).")

    def check_owner(self, actor, donation, permission):
        check_permission(actor, permission)
        if donation.donor_id != actor.user_id:
            raise AuthorizationError("You can only modify your own donations.")

    def create(self, actor, food_name, category, quantity, unit, expiry_date, city,
               pickup_location, pickup_from, pickup_until, notes=""):
        check_permission(actor, "create_donation")
        fields = self.check_fields(food_name, category, quantity, unit, expiry_date, city,
                                   pickup_location, pickup_from, pickup_until, notes)
        self.check_duplicate(actor.user_id, fields)
        donation = Donation(self.new_id(), actor.user_id, **fields)
        self.add_record(donation)
        self.save()
        return donation

    def edit(self, actor, donation_id, food_name, category, quantity, unit, expiry_date, city,
             pickup_location, pickup_from, pickup_until, notes=""):
        donation = self.get(donation_id)
        self.check_owner(actor, donation, "edit_own_donation")
        self.expire_overdue()
        if not donation.is_pending():
            raise InvalidStateError(f"Donation {donation.donation_id} is {donation.status} and can no longer be edited.")
        fields = self.check_fields(food_name, category, quantity, unit, expiry_date, city,
                                   pickup_location, pickup_from, pickup_until, notes)
        self.check_duplicate(donation.donor_id, fields, donation.donation_id)
        for name, value in fields.items():
            setattr(donation, name, value)
        donation.updated_at = now_text()
        self.save()
        return donation

    def cancel(self, actor, donation_id, reason):
        donation = self.get(donation_id)
        check_permission(actor)
        if not actor.can("cancel_any_donation"):
            self.check_owner(actor, donation, "cancel_own_donation")
        self.expire_overdue()
        if not donation.is_pending():
            raise InvalidStateError(f"Donation {donation.donation_id} is {donation.status} and cannot be cancelled.")
        donation.cancel_reason = clean_text(reason, "Cancellation reason", 3, 200)
        donation.status = "Cancelled"
        donation.updated_at = now_text()
        self.save()
        return donation

    def get(self, donation_id):
        donation_id = validate_donation_id(donation_id)
        if donation_id not in self.records:
            raise NotFoundError(f"Donation {donation_id} was not found.")
        return self.records[donation_id]

    def list_visible(self, actor):
        check_permission(actor)
        if actor.can("view_all_donations"):
            return list(self.records.values())
        if actor.can("view_own_donations"):
            return [self.records[i] for i in self.by_donor.get(actor.user_id, [])]
        raise AuthorizationError("Your role cannot view donations on this page.")

    def status_counts(self, donations):
        counts = {status: 0 for status in config.statuses}
        for donation in donations:
            counts[donation.status] += 1
        return counts

    def all_donations(self):
        return list(self.records.values())

    def pending_donations(self):
        return [d for d in self.records.values() if d.is_pending()]

    def set_status(self, donation_id, new_status, ngo_id=None):
        donation = self.get(donation_id)
        donation.status = validate_choice(new_status, config.statuses, "Status")
        if ngo_id is not None:
            donation.ngo_id = str(ngo_id)
        donation.updated_at = now_text()
        self.save()
        return donation

    def expire_overdue(self):
        changed = False
        for donation in self.records.values():
            if donation.is_pending() and donation.days_to_expiry() < 0:
                donation.status = "Expired"
                donation.updated_at = now_text()
                changed = True
        if changed:
            self.save()
