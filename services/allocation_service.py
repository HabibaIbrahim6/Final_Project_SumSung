import copy
import json
import math
import os
from datetime import datetime, time

import config
from algorithms.distance_matrix import DistanceMatrix
from algorithms.greedy_allocation import GreedyAllocation
from algorithms.priority_queue import PriorityQueue
from algorithms.stack import Stack
from models import check_permission
from validators import (DuplicateError, InvalidStateError, NotFoundError, ValidationError,
                        clean_text, validate_choice)

all_foods = list(config.food_categories)

default_ngos = [
    {"id": 1, "name": "Cairo Food Bank", "location": "Cairo", "pickup_time_minutes": 20,
     "accepted_food_types": all_foods,
     "remaining_capacity": {"kg": 300, "portions": 400, "liters": 100, "boxes": 200, "items": 300}},
    {"id": 2, "name": "Giza Hope Kitchen", "location": "Giza", "pickup_time_minutes": 15,
     "accepted_food_types": ["Cooked Meals", "Dairy", "Fruits & Vegetables", "Packaged Food", "Beverages"],
     "remaining_capacity": {"kg": 200, "portions": 150, "liters": 60, "boxes": 80}},
    {"id": 3, "name": "Fayoum Relief", "location": "Fayoum", "pickup_time_minutes": 35,
     "accepted_food_types": ["Cooked Meals", "Fruits & Vegetables", "Bakery", "Packaged Food"],
     "remaining_capacity": {"kg": 250, "portions": 120, "boxes": 60, "items": 150}},
    {"id": 4, "name": "Bread for All", "location": "Cairo", "pickup_time_minutes": 10,
     "accepted_food_types": ["Bakery"],
     "remaining_capacity": {"items": 200, "kg": 60, "boxes": 40}},
    {"id": 5, "name": "Alex Food Share", "location": "Alexandria", "pickup_time_minutes": 30,
     "accepted_food_types": ["Cooked Meals", "Bakery", "Fruits & Vegetables", "Dairy", "Packaged Food"],
     "remaining_capacity": {"kg": 200, "portions": 150, "liters": 50, "boxes": 80}},
]

default_matrix = DistanceMatrix(
    list(config.cities),
    [1, 2, 3, 4, 5],
    [
        [5, 18, 100, 6, 220],
        [20, 4, 85, 21, 210],
        [100, 90, 6, 102, 300],
        [220, 210, 300, 222, 6],
    ],
)


def to_item(donation):
    deadline = datetime.combine(donation.expiry_date, time(23, 59))
    minutes = max(0, int((deadline - datetime.now()).total_seconds() // 60))
    return {
        "id": int(donation.donation_id.split("-")[1]),
        "ref": donation.donation_id,
        "food_name": donation.food_name,
        "food_type": donation.category,
        "quantity": donation.quantity,
        "unit": donation.unit,
        "minutes_to_expiry": minutes,
        "status": donation.status,
        "donor_location": donation.city,
        "pickup_location": donation.pickup_location,
        "ngo_id": int(donation.ngo_id) if str(donation.ngo_id).isdigit() else None,
    }


class AllocationService:
    def __init__(self, donation_service, path=None, matrix=None):
        self.donation_service = donation_service
        self.path = path or config.ngos_file
        self.matrix = matrix or default_matrix
        self.greedy = GreedyAllocation(self.matrix)
        self.history = Stack()
        self.proposals = []
        self.queue = PriorityQueue()
        self.ngos = []
        self.load_ngos()
        self.refresh_queue()

    def load_ngos(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as file:
                self.ngos = json.load(file)
        else:
            self.ngos = copy.deepcopy(default_ngos)
            self.save_ngos()

    def save_ngos(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(self.ngos, file, indent=2, ensure_ascii=False)

    def ngo_by_id(self, ngo_id):
        for ngo in self.ngos:
            if str(ngo["id"]) == str(ngo_id):
                return ngo
        raise NotFoundError(f"NGO {ngo_id} was not found.")

    def ngo_for_user(self, actor):
        check_permission(actor, "manage_ngo_profile")
        ngo_id = getattr(actor, "ngo_id", "")
        if not ngo_id:
            raise InvalidStateError(
                "Your NGO account is waiting for an administrator to link it to a registered NGO."
            )
        return self.ngo_by_id(ngo_id)

    def update_ngo_profile(self, actor, name, location, pickup_time_minutes,
                           accepted_food_types, remaining_capacity, ngo_id=None):
        check_permission(actor)
        if actor.can("manage_ngos"):
            if ngo_id is None:
                raise ValidationError("Select an NGO profile to update.")
            ngo = self.ngo_by_id(ngo_id)
        else:
            check_permission(actor, "manage_ngo_profile")
            ngo = self.ngo_for_user(actor)
        name = clean_text(name, "NGO name", 2, 100)
        location = validate_choice(location, config.cities, "City")
        if any(
            other["id"] != ngo["id"]
            and other["name"].strip().casefold() == name.casefold()
            for other in self.ngos
        ):
            raise DuplicateError("An NGO with this name already exists.")
        try:
            preparation_minutes = float(pickup_time_minutes)
        except (TypeError, ValueError) as error:
            raise ValidationError("Pickup preparation time must be a whole number.") from error
        if (isinstance(pickup_time_minutes, bool)
                or not math.isfinite(preparation_minutes)
                or preparation_minutes < 0
                or not preparation_minutes.is_integer()):
            raise ValidationError("Pickup preparation time must be a non-negative whole number.")
        if not accepted_food_types:
            raise ValidationError("Select at least one accepted food category.")
        for food in accepted_food_types:
            validate_choice(food, config.food_categories, "Food category")

        capacities = {}
        for unit in config.units:
            try:
                value = float(remaining_capacity.get(unit, 0))
            except (AttributeError, TypeError, ValueError) as error:
                raise ValidationError(f"Capacity for {unit} must be a number.") from error
            if not math.isfinite(value) or value < 0:
                raise ValidationError(f"Capacity for {unit} must be zero or greater.")
            capacities[unit] = round(value, 2)

        ngo["name"] = name
        ngo["location"] = location
        ngo["pickup_time_minutes"] = int(preparation_minutes)
        ngo["accepted_food_types"] = list(accepted_food_types)
        ngo["remaining_capacity"] = capacities
        self.save_ngos()
        return ngo

    def eligible_donations(self, actor):
        check_permission(actor, "view_eligible_donations")
        ngo = self.ngo_for_user(actor)
        eligible = []
        for donation in self.donation_service.pending_donations():
            item = to_item(donation)
            if self.greedy.check(item, ngo)[0]:
                eligible.append(donation)
        return eligible

    def assigned_donations(self, actor):
        check_permission(actor, "view_eligible_donations")
        ngo = self.ngo_for_user(actor)
        return [
            donation for donation in self.donation_service.all_donations()
            if str(donation.ngo_id) == str(ngo["id"])
            and donation.status in ("Allocated", "Delivered")
        ]

    def mark_delivered(self, actor, ref):
        check_permission(actor, "respond_to_offers")
        ngo = self.ngo_for_user(actor)
        donation = self.donation_service.get(ref)
        if str(donation.ngo_id) != str(ngo["id"]):
            raise InvalidStateError("This donation is not assigned to your NGO.")
        if donation.status != "Allocated":
            raise InvalidStateError(
                f"Donation {donation.donation_id} is {donation.status} and cannot be marked delivered."
            )
        return self.donation_service.set_status(ref, "Delivered")

    def release_assignment(self, actor, ref):
        check_permission(actor, "approve_allocations")
        donation = self.donation_service.get(ref)
        if donation.status != "Allocated":
            raise InvalidStateError(
                f"Donation {donation.donation_id} is {donation.status} and cannot be released."
            )
        ngo = self.ngo_by_id(donation.ngo_id)
        self.greedy.restore(ngo, donation.unit, donation.quantity)
        self.donation_service.set_status(ref, "Pending", "")
        self.save_ngos()
        self.history.items = [entry for entry in self.history.items if entry["ref"] != ref]
        for proposal in self.proposals:
            if proposal["ref"] == ref and proposal["status"] == "Approved":
                proposal["status"] = "Reverted"
        return donation

    def all_items(self):
        self.donation_service.expire_overdue()
        return [to_item(d) for d in self.donation_service.all_donations()]

    def find_item(self, ref):
        return to_item(self.donation_service.get(ref))

    def refresh_queue(self):
        self.donation_service.expire_overdue()
        self.queue = PriorityQueue()
        for donation in self.donation_service.pending_donations():
            self.queue.push(to_item(donation))

    def get_pending_queue(self):
        self.refresh_queue()
        return self.queue.to_sorted_list()

    def next_item(self):
        self.refresh_queue()
        return self.queue.peek()

    def recommend(self, ref=None):
        item = self.next_item() if ref is None else self.find_item(ref)
        if item is None:
            return None
        result = self.greedy.recommend(item, self.ngos)
        result["donation"] = item
        return result

    def propose(self, actor, ref):
        check_permission(actor, "manage_allocations")
        donation = self.donation_service.get(ref)
        if not donation.is_pending():
            raise InvalidStateError(f"Donation {donation.donation_id} is {donation.status}.")
        if self.has_open_proposal(donation.donation_id):
            raise DuplicateError("This donation was already sent to the admin.")
        result = self.greedy.recommend(to_item(donation), self.ngos)
        if result["ngo"] is None:
            raise NotFoundError("No NGO can take this donation in time.")
        proposal = {"ref": donation.donation_id, "ngo_id": result["ngo"]["id"],
                    "reasons": result["reasons"], "total_minutes": result["total_minutes"],
                    "proposed_by": actor.full_name, "status": "Pending"}
        self.proposals.append(proposal)
        return proposal

    def has_open_proposal(self, ref):
        return any(p["ref"] == ref for p in self.open_proposals())

    def open_proposals(self):
        result = []
        for proposal in self.proposals:
            if proposal["status"] != "Pending":
                continue
            if not self.donation_service.get(proposal["ref"]).is_pending():
                proposal["status"] = "Outdated"
                continue
            result.append(proposal)
        return result

    def count_proposals(self, status):
        return len([p for p in self.proposals if p["status"] == status])

    def find_open_proposal(self, ref):
        for proposal in self.open_proposals():
            if proposal["ref"] == ref:
                return proposal
        raise NotFoundError(f"No open proposal for {ref}.")

    def approve(self, actor, ref):
        check_permission(actor, "approve_allocations")
        proposal = self.find_open_proposal(ref)
        self.confirm(ref, proposal["ngo_id"])
        proposal["status"] = "Approved"
        proposal["reviewed_by"] = actor.full_name
        return proposal

    def reject(self, actor, ref):
        check_permission(actor, "approve_allocations")
        proposal = self.find_open_proposal(ref)
        proposal["status"] = "Rejected"
        proposal["reviewed_by"] = actor.full_name
        return proposal

    def confirm(self, ref, ngo_id):
        donation = self.donation_service.get(ref)
        self.donation_service.expire_overdue()
        if not donation.is_pending():
            raise InvalidStateError(f"Donation {donation.donation_id} is {donation.status}.")
        ngo = self.ngo_by_id(ngo_id)
        item = to_item(donation)
        ok, reason = self.greedy.check(item, ngo)
        if not ok:
            raise InvalidStateError(f"{ngo['name']} {reason}.")
        self.greedy.consume(ngo, item["unit"], item["quantity"])
        self.donation_service.set_status(ref, "Allocated", ngo_id)
        self.save_ngos()
        self.history.push({"ref": ref, "ngo_id": ngo_id, "unit": item["unit"],
                           "quantity": item["quantity"]})
        return donation

    def undo_last(self, actor):
        check_permission(actor, "approve_allocations")
        last = self.history.peek()
        if last is None:
            raise InvalidStateError("Nothing to undo.")
        donation = self.donation_service.get(last["ref"])
        if donation.status != "Allocated":
            raise InvalidStateError(f"Donation {donation.donation_id} is {donation.status} and cannot be undone.")
        self.history.pop()
        self.greedy.restore(self.ngo_by_id(last["ngo_id"]), last["unit"], last["quantity"])
        self.donation_service.set_status(last["ref"], "Pending", "")
        self.save_ngos()
        for proposal in self.proposals:
            if proposal["ref"] == last["ref"] and proposal["status"] == "Approved":
                proposal["status"] = "Reverted"
        return last

    def history_rows(self):
        names = {n["id"]: n["name"] for n in self.ngos}
        return [{"ref": h["ref"], "ngo": names.get(h["ngo_id"], str(h["ngo_id"])),
                 "quantity": f'{h["quantity"]:g} {h["unit"]}'} for h in self.history.to_list()]

    def compare_with_baseline(self):
        queue = self.get_pending_queue()
        out = {}
        for name in ("greedy", "baseline"):
            ngos = copy.deepcopy(self.ngos)
            engine = GreedyAllocation(self.matrix)
            allocated, minutes, km = 0, 0.0, 0.0
            for item in queue:
                ngo = (engine.recommend_ngo(item, ngos) if name == "greedy"
                       else engine.baseline_recommend(item, ngos))
                if ngo is None:
                    continue
                engine.consume(ngo, item["unit"], item["quantity"])
                allocated += 1
                minutes += engine.total_minutes(item, ngo)
                km += engine.distance_km(item, ngo)
            out[name] = {
                "allocated": allocated,
                "unallocated": len(queue) - allocated,
                "avg_minutes": round(minutes / allocated, 1) if allocated else 0,
                "total_km": round(km, 1),
            }
        return out
