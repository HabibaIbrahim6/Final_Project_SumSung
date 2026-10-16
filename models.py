from datetime import date, datetime

import config
from validators import AuthenticationError, AuthorizationError, ValidationError


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class User:
    role = "user"
    label = "User"
    permissions = set()
    pages = ()

    def __init__(self, user_id, full_name, email, phone, password, created_at=None, is_active=True):
        self.user_id = user_id
        self.full_name = full_name
        self.email = email
        self.phone = phone
        self.password = password
        self.created_at = created_at or now_text()
        self.is_active = is_active

    def can(self, permission):
        return permission in self.permissions

    def welcome_message(self):
        return f"{self.full_name} ({self.label})"

    def to_dict(self):
        data = dict(vars(self))
        data["role"] = self.role
        return data


class Donor(User):
    role = "donor"
    label = config.role_labels["donor"]
    permissions = {"create_donation", "edit_own_donation", "cancel_own_donation",
                   "view_own_donations"}
    pages = ("create_donation", "my_donations", "impact_report")

    def __init__(self, user_id, full_name, email, phone, password, created_at=None,
                 is_active=True, donor_type="Other", organization=""):
        super().__init__(user_id, full_name, email, phone, password, created_at, is_active)
        self.donor_type = donor_type
        self.organization = organization

    def welcome_message(self):
        name = self.organization or self.full_name
        return f"{name} ({self.donor_type} donor)"


class NGOUser(User):
    role = "ngo"
    label = config.role_labels["ngo"]
    permissions = {"manage_ngo_profile", "view_eligible_donations", "respond_to_offers"}
    pages = ("ngo_dashboard", "ngo_profile", "tracking", "impact_report")

    def __init__(self, user_id, full_name, email, phone, password, created_at=None,
                 is_active=True, ngo_id=""):
        super().__init__(user_id, full_name, email, phone, password, created_at, is_active)
        self.ngo_id = str(ngo_id or "")


class Coordinator(User):
    role = "coordinator"
    label = config.role_labels["coordinator"]
    permissions = {"view_all_donations", "manage_allocations", "manage_distribution",
                   "view_analytics"}
    pages = ("my_donations", "explorer", "smart_allocation", "tracking",
             "analytics", "impact_report")


class AdminUser(Coordinator):
    role = "admin"
    label = config.role_labels["admin"]
    permissions = Coordinator.permissions | {"manage_users", "manage_ngos", "cancel_any_donation",
                                             "approve_allocations"}
    pages = Coordinator.pages + (
        "admin_allocations",
        "admin_distributions",
        "admin_users",
        "admin_ngos",
    )


user_classes = {"donor": Donor, "ngo": NGOUser, "coordinator": Coordinator, "admin": AdminUser}


def create_user(record):
    data = dict(record)
    role = data.pop("role")
    if role not in user_classes:
        raise ValidationError(f"Unknown user role: {role}")
    return user_classes[role](**data)


def check_permission(actor, permission=None):
    if actor is None:
        raise AuthenticationError("You must be logged in to do this.")
    if not actor.is_active:
        raise AuthorizationError("Your account is deactivated.")
    if permission and not actor.can(permission):
        raise AuthorizationError(f"Your role ({actor.label}) is not allowed to do this.")


class Donation:
    def __init__(self, donation_id, donor_id, food_name, category, quantity, unit,
                 expiry_date, pickup_location, pickup_from, pickup_until, notes="",
                 status="Pending", cancel_reason="", created_at=None, updated_at=None,
                 city="Cairo", ngo_id=""):
        self.donation_id = donation_id
        self.donor_id = donor_id
        self.food_name = food_name
        self.category = category
        self.quantity = quantity
        self.unit = unit
        self.expiry_date = expiry_date
        self.pickup_location = pickup_location
        self.pickup_from = pickup_from
        self.pickup_until = pickup_until
        self.notes = notes
        self.status = status
        self.cancel_reason = cancel_reason
        self.created_at = created_at or now_text()
        self.updated_at = updated_at or self.created_at
        self.city = city or "Cairo"
        self.ngo_id = ngo_id or ""

    def is_pending(self):
        return self.status == "Pending"

    def days_to_expiry(self):
        return (self.expiry_date - date.today()).days

    def matches(self, query):
        needle = query.strip().lower()
        for text in (self.donation_id, self.food_name, self.category, self.pickup_location):
            if needle in text.lower():
                return True
        return False

    def to_row(self):
        row = dict(vars(self))
        row["quantity"] = f"{self.quantity:.2f}"
        row["expiry_date"] = self.expiry_date.isoformat()
        return row


def donation_from_row(row):
    data = dict(row)
    data["quantity"] = float(data["quantity"])
    data["expiry_date"] = date.fromisoformat(data["expiry_date"])
    if data["status"] not in config.statuses:
        raise ValueError("unknown status")
    return Donation(**data)
