"""Distribution lifecycle, capacity checks, undo, and CSV persistence."""

import csv
from datetime import datetime
from pathlib import Path

from services.distribution import (
    ACTIVE_STATUSES,
    ALL_STATUSES,
    CANCELLED,
    CONFIRMED,
    DELIVERED,
    DISTRIBUTION_COLUMNS,
    FAILED,
    IN_TRANSIT,
    PROPOSED,
    CapacityExceededError,
    Distribution,
    DistributionError,
    DuplicateDistributionError,
    UnknownRecordError,
    clean_id,
    now_str,
    parse_kg,
)
from services.history_stack import EmptyStackError, HistoryStack

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DISTRIBUTIONS_CSV = BASE_DIR / "data" / "distributions.csv"
DEFAULT_LOG_CSV = BASE_DIR / "data" / "distribution_log.csv"
LOG_COLUMNS = ["distribution_id", "timestamp", "from_status", "to_status", "note"]


def _read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TrackingService:
    def __init__(
        self,
        distributions_path=DEFAULT_DISTRIBUTIONS_CSV,
        log_path=DEFAULT_LOG_CSV,
        auto_save=False,
        history_limit=50,
    ):
        self.distributions_path = Path(distributions_path)
        self.log_path = Path(log_path)
        self.auto_save = auto_save
        self.skipped_rows = 0
        self._records = {}
        self._donation_totals = {}
        self._ngo_capacities = {}
        self._history = HistoryStack(max_size=history_limit)
        self.load()

    def register_donation(self, donation_id, quantity_kg):
        self._donation_totals[clean_id(donation_id, "donation_id")] = parse_kg(
            quantity_kg, "quantity_kg"
        )

    def register_ngo(self, ngo_id, capacity_kg):
        self._ngo_capacities[clean_id(ngo_id, "ngo_id")] = parse_kg(
            capacity_kg, "capacity_kg", allow_zero=True
        )

    def donation_remaining_kg(self, donation_id):
        if donation_id not in self._donation_totals:
            raise UnknownRecordError(f"Donation {donation_id!r} is not registered.")
        used = sum(
            record.reserved_kg for record in self._records.values()
            if record.donation_id == donation_id
        )
        return round(self._donation_totals[donation_id] - used, 3)

    def ngo_remaining_capacity_kg(self, ngo_id):
        if ngo_id not in self._ngo_capacities:
            raise UnknownRecordError(f"NGO {ngo_id!r} is not registered.")
        used = sum(
            record.reserved_kg for record in self._records.values()
            if record.ngo_id == ngo_id
        )
        return round(self._ngo_capacities[ngo_id] - used, 3)

    def _check_capacity(self, donation_id, ngo_id, quantity):
        left_food = self.donation_remaining_kg(donation_id)
        if quantity > left_food:
            raise CapacityExceededError(
                f"Only {left_food} kg of donation {donation_id} is still available "
                f"(requested {quantity} kg)."
            )
        left_capacity = self.ngo_remaining_capacity_kg(ngo_id)
        if quantity > left_capacity:
            raise CapacityExceededError(
                f"NGO {ngo_id} has only {left_capacity} kg of free capacity "
                f"(requested {quantity} kg)."
            )

    def _next_id(self):
        numbers = [int(key.split("-")[1]) for key in self._records]
        return f"DIS-{(max(numbers) + 1 if numbers else 1):04d}"

    def _push(self, action, distribution_id, before, after_status):
        self._history.push(
            {
                "action": action,
                "distribution_id": distribution_id,
                "before": before,
                "after_status": after_status,
                "timestamp": now_str(),
            }
        )

    def create_distribution(self, donation_id, ngo_id, allocated_quantity_kg):
        donation_id = clean_id(donation_id, "donation_id")
        ngo_id = clean_id(ngo_id, "ngo_id")
        quantity = parse_kg(allocated_quantity_kg, "allocated_quantity_kg")
        self._check_capacity(donation_id, ngo_id, quantity)
        for record in self._records.values():
            if (
                record.donation_id == donation_id
                and record.ngo_id == ngo_id
                and record.status in ACTIVE_STATUSES
            ):
                raise DuplicateDistributionError(
                    f"{record.distribution_id} already links donation {donation_id} "
                    f"to NGO {ngo_id} and is still {record.status}."
                )
        record = Distribution(self._next_id(), donation_id, ngo_id, quantity)
        self._records[record.distribution_id] = record
        self._push("create", record.distribution_id, None, record.status)
        self._persist()
        return record

    def import_allocation(self, donation_id, ngo_id, allocated_quantity_kg, delivered=False):
        """Seed a record for an allocation that predates distribution tracking."""
        donation_id = clean_id(donation_id, "donation_id")
        ngo_id = clean_id(ngo_id, "ngo_id")
        quantity = parse_kg(allocated_quantity_kg, "allocated_quantity_kg")
        self._check_capacity(donation_id, ngo_id, quantity)
        for record in self._records.values():
            if (
                record.donation_id == donation_id
                and record.ngo_id == ngo_id
                and record.status in ACTIVE_STATUSES
            ):
                raise DuplicateDistributionError(
                    f"{record.distribution_id} already links donation {donation_id} "
                    f"to NGO {ngo_id} and is still {record.status}."
                )
        record = Distribution(self._next_id(), donation_id, ngo_id, quantity)
        record.change_status(CONFIRMED, "Imported from the approved allocation.")
        if delivered:
            record.change_status(IN_TRANSIT, "Imported delivery state.")
            record.change_status(DELIVERED, "Imported delivered allocation.", quantity)
        self._records[record.distribution_id] = record
        self._persist()
        return record

    def _transition(self, distribution_id, new_status, action, note="", delivered_quantity_kg=None):
        record = self.get(distribution_id)
        before = record.snapshot()
        if record.status == PROPOSED and new_status == CONFIRMED:
            self._check_capacity(record.donation_id, record.ngo_id, record.allocated_quantity_kg)
        record.change_status(new_status, note, delivered_quantity_kg)
        self._push(action, distribution_id, before, record.status)
        self._persist()
        return record

    def confirm(self, distribution_id, note=""):
        return self._transition(distribution_id, CONFIRMED, "confirm", note)

    def start_transit(self, distribution_id, note=""):
        return self._transition(distribution_id, IN_TRANSIT, "start transit", note)

    def mark_delivered(self, distribution_id, delivered_quantity_kg=None, note=""):
        return self._transition(
            distribution_id, DELIVERED, "deliver", note, delivered_quantity_kg
        )

    def cancel(self, distribution_id, reason):
        return self._transition(distribution_id, CANCELLED, "cancel", reason)

    def fail(self, distribution_id, reason):
        return self._transition(distribution_id, FAILED, "fail", reason)

    def undo_last(self):
        try:
            entry = self._history.pop()
        except EmptyStackError as error:
            raise DistributionError("There is nothing to undo.") from error
        distribution_id = entry["distribution_id"]
        current = self._records.get(distribution_id)
        if current is None or current.status != entry["after_status"]:
            self._history.push(entry)
            raise DistributionError(
                f"Cannot undo: {distribution_id} changed outside the tracked history."
            )
        if entry["before"] is None:
            del self._records[distribution_id]
        else:
            self._records[distribution_id] = entry["before"]
        self._persist()
        return f"Undid '{entry['action']}' on {distribution_id}."

    def last_action_description(self):
        if self._history.is_empty():
            return None
        entry = self._history.peek()
        return f"{entry['action']} on {entry['distribution_id']} ({entry['timestamp']})"

    def history_entries(self):
        return [
            {
                "action": entry["action"],
                "distribution_id": entry["distribution_id"],
                "timestamp": entry["timestamp"],
            }
            for entry in self._history.as_list()
        ]

    def get(self, distribution_id):
        if distribution_id not in self._records:
            raise UnknownRecordError(f"Distribution {distribution_id!r} does not exist.")
        return self._records[distribution_id]

    def list_distributions(self, status=None, ngo_id=None, donation_ids=None):
        wanted = set(donation_ids) if donation_ids is not None else None
        return [
            record
            for record in self._records.values()
            if (status is None or record.status == status)
            and (ngo_id is None or record.ngo_id == ngo_id)
            and (wanted is None or record.donation_id in wanted)
        ]

    def status_counts(self, records=None):
        records = self._records.values() if records is None else records
        counts = {status: 0 for status in ALL_STATUSES}
        for record in records:
            counts[record.status] += 1
        return counts

    @staticmethod
    def summarize(records):
        records = list(records)
        allocated = sum(record.allocated_quantity_kg for record in records if record.status != CANCELLED)
        delivered = sum(record.delivered_quantity_kg for record in records if record.status == DELIVERED)
        in_flight = sum(
            record.allocated_quantity_kg
            for record in records
            if record.status in (CONFIRMED, IN_TRANSIT)
        )
        finished = [record for record in records if record.status in (DELIVERED, FAILED)]
        success = (
            sum(record.status == DELIVERED for record in finished) / len(finished)
            if finished
            else 0.0
        )
        return {
            "total": len(records),
            "allocated_kg": round(allocated, 3),
            "delivered_kg": round(delivered, 3),
            "in_flight_kg": round(in_flight, 3),
            "success_rate": round(success, 3),
        }

    def stalled(self, hours=24, now=None):
        now = now or datetime.now()
        return [
            record
            for record in self._records.values()
            if record.status in (CONFIRMED, IN_TRANSIT)
            and (now - datetime.strptime(record.last_change_at, "%Y-%m-%d %H:%M:%S"))
            .total_seconds() > hours * 3600
        ]

    def _persist(self):
        if self.auto_save:
            self.save()

    def save(self):
        self.distributions_path.parent.mkdir(parents=True, exist_ok=True)
        with self.distributions_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=DISTRIBUTION_COLUMNS)
            writer.writeheader()
            for record in self._records.values():
                writer.writerow(record.to_dict())
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=LOG_COLUMNS)
            writer.writeheader()
            for record in self._records.values():
                for entry in record.status_history:
                    writer.writerow({"distribution_id": record.distribution_id, **entry})

    def load(self):
        self._records = {}
        self.skipped_rows = 0
        for row in _read_csv(self.distributions_path):
            try:
                record = Distribution.from_dict(row)
            except DistributionError:
                self.skipped_rows += 1
                continue
            if record.distribution_id in self._records:
                self.skipped_rows += 1
                continue
            self._records[record.distribution_id] = record
        grouped = {}
        for row in _read_csv(self.log_path):
            grouped.setdefault(row.get("distribution_id"), []).append(
                {key: row.get(key, "") for key in LOG_COLUMNS[1:]}
            )
        for distribution_id, entries in grouped.items():
            if distribution_id in self._records:
                self._records[distribution_id].status_history = entries
        self._history.clear()
        return len(self._records)
