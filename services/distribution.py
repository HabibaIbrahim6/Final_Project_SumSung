"""Distribution records and the allowed delivery lifecycle."""

import copy
import math
import re
from datetime import datetime

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
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
ID_PATTERN = re.compile(r"^DIS-\d{4,}$")

PROPOSED = "proposed"
CONFIRMED = "confirmed"
IN_TRANSIT = "in_transit"
DELIVERED = "delivered"
CANCELLED = "cancelled"
FAILED = "failed"

ALL_STATUSES = (PROPOSED, CONFIRMED, IN_TRANSIT, DELIVERED, CANCELLED, FAILED)
TERMINAL_STATUSES = frozenset({DELIVERED, CANCELLED, FAILED})
ACTIVE_STATUSES = frozenset({PROPOSED, CONFIRMED, IN_TRANSIT})
ALLOWED_TRANSITIONS = {
    PROPOSED: frozenset({CONFIRMED, CANCELLED}),
    CONFIRMED: frozenset({IN_TRANSIT, CANCELLED}),
    IN_TRANSIT: frozenset({DELIVERED, FAILED}),
    DELIVERED: frozenset(),
    CANCELLED: frozenset(),
    FAILED: frozenset(),
}
REASON_REQUIRED = frozenset({CANCELLED, FAILED})


class DistributionError(Exception):
    """Base exception for distribution workflow errors."""


class InvalidStatusTransition(DistributionError):
    pass


class InvalidQuantityError(DistributionError):
    pass


class CapacityExceededError(DistributionError):
    pass


class UnknownRecordError(DistributionError):
    pass


class DuplicateDistributionError(DistributionError):
    pass


def now_str():
    return datetime.now().strftime(DATE_FORMAT)


def clean_id(value, field):
    text = "" if value is None else str(value).strip()
    if not text:
        raise DistributionError(f"{field} is required.")
    return text


def parse_kg(value, field, allow_zero=False):
    if isinstance(value, bool):
        raise InvalidQuantityError(f"{field} must be a number, got {value!r}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise InvalidQuantityError(f"{field} must be a number, got {value!r}.") from error
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        raise InvalidQuantityError(f"{field} must be a positive finite number.")
    return round(number, 3)


def _blank(value):
    return value is None or str(value).strip().lower() in ("", "nan", "none", "nat")


class Distribution:
    """One allocation of a donation to one NGO."""

    def __init__(
        self,
        distribution_id,
        donation_id,
        ngo_id,
        allocated_quantity_kg,
        delivered_quantity_kg=0.0,
        allocated_at=None,
        delivered_at=None,
        status=PROPOSED,
        status_history=None,
    ):
        if not isinstance(distribution_id, str) or not ID_PATTERN.fullmatch(distribution_id):
            raise DistributionError(
                f"Invalid distribution id {distribution_id!r}; expected a format like DIS-0001."
            )
        if status not in ALL_STATUSES:
            raise DistributionError(f"Unknown status {status!r}.")
        self.distribution_id = distribution_id
        self.donation_id = clean_id(donation_id, "donation_id")
        self.ngo_id = clean_id(ngo_id, "ngo_id")
        self.allocated_quantity_kg = parse_kg(allocated_quantity_kg, "allocated_quantity_kg")
        self.delivered_quantity_kg = parse_kg(
            delivered_quantity_kg, "delivered_quantity_kg", allow_zero=True
        )
        if self.delivered_quantity_kg > self.allocated_quantity_kg:
            raise InvalidQuantityError("Delivered quantity cannot exceed the allocated quantity.")
        self.status = status
        self.allocated_at = allocated_at or now_str()
        self.delivered_at = delivered_at or None
        self.status_history = status_history or [
            {
                "timestamp": self.allocated_at,
                "from_status": "",
                "to_status": status,
                "note": "Distribution created",
            }
        ]

    @property
    def is_terminal(self):
        return self.status in TERMINAL_STATUSES

    @property
    def reserved_kg(self):
        if self.status in (CONFIRMED, IN_TRANSIT):
            return self.allocated_quantity_kg
        if self.status == DELIVERED:
            return self.delivered_quantity_kg
        return 0.0

    @property
    def last_change_at(self):
        return self.status_history[-1]["timestamp"] if self.status_history else self.allocated_at

    def can_transition_to(self, new_status):
        return new_status in ALLOWED_TRANSITIONS.get(self.status, frozenset())

    def next_statuses(self):
        return sorted(ALLOWED_TRANSITIONS.get(self.status, frozenset()))

    def change_status(self, new_status, note="", delivered_quantity_kg=None):
        if new_status not in ALL_STATUSES:
            raise DistributionError(f"Unknown status {new_status!r}.")
        if not self.can_transition_to(new_status):
            allowed = ", ".join(self.next_statuses()) or "none (final state)"
            raise InvalidStatusTransition(
                f"{self.distribution_id}: cannot move from '{self.status}' to "
                f"'{new_status}'. Allowed next steps: {allowed}."
            )
        note = (note or "").strip()
        if new_status in REASON_REQUIRED and not note:
            raise DistributionError(f"A reason is required to mark a distribution as {new_status}.")

        quantity = None
        if new_status == DELIVERED:
            quantity = (
                self.allocated_quantity_kg
                if delivered_quantity_kg is None
                else parse_kg(delivered_quantity_kg, "delivered_quantity_kg")
            )
            if quantity > self.allocated_quantity_kg:
                raise InvalidQuantityError("Delivered quantity cannot exceed the allocated quantity.")
            if quantity < self.allocated_quantity_kg:
                note = (note + " " if note else "") + (
                    f"Partial delivery: {quantity} of {self.allocated_quantity_kg} kg."
                )

        timestamp = now_str()
        previous = self.status
        if quantity is not None:
            self.delivered_quantity_kg = quantity
            self.delivered_at = timestamp
        self.status = new_status
        self.status_history.append(
            {
                "timestamp": timestamp,
                "from_status": previous,
                "to_status": new_status,
                "note": note,
            }
        )

    def snapshot(self):
        return copy.deepcopy(self)

    def to_dict(self):
        return {
            "distribution_id": self.distribution_id,
            "donation_id": self.donation_id,
            "ngo_id": self.ngo_id,
            "allocated_quantity_kg": self.allocated_quantity_kg,
            "delivered_quantity_kg": self.delivered_quantity_kg,
            "allocated_at": self.allocated_at,
            "delivered_at": self.delivered_at or "",
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, row):
        status = "" if _blank(row.get("status")) else str(row["status"]).strip().lower().replace(" ", "_")
        return cls(
            distribution_id=str(row.get("distribution_id", "")).strip(),
            donation_id=row.get("donation_id"),
            ngo_id=row.get("ngo_id"),
            allocated_quantity_kg=row.get("allocated_quantity_kg"),
            delivered_quantity_kg=(
                0.0 if _blank(row.get("delivered_quantity_kg")) else row["delivered_quantity_kg"]
            ),
            allocated_at=None if _blank(row.get("allocated_at")) else str(row["allocated_at"]),
            delivered_at=None if _blank(row.get("delivered_at")) else str(row["delivered_at"]),
            status=status or PROPOSED,
        )
