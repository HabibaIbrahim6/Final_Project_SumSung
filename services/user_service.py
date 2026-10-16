import json
import os

import config
from models import check_permission, create_user, now_text
from validators import (AuthenticationError, AuthorizationError, DuplicateError, NotFoundError,
                        ValidationError, validate_choice, validate_email, validate_name, validate_password,
                        validate_phone, validate_user_id)


class UserService:
    def __init__(self, path=None):
        self.path = path or config.users_file
        self.records = {}
        self.ids = set()
        self.emails = set()
        self.load()
        self.ensure_admin()

    def load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as file:
            for record in json.load(file):
                self.add_record(record)

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(list(self.records.values()), file, indent=2, ensure_ascii=False)

    def add_record(self, record):
        user_id = validate_user_id(record["user_id"])
        email = record["email"].lower()
        if user_id in self.ids or email in self.emails:
            raise DuplicateError("Duplicate user ID or email.")
        self.records[user_id] = record
        self.ids.add(user_id)
        self.emails.add(email)

    def new_id(self):
        number = len(self.ids) + 1
        while f"USR-{number:04d}" in self.ids:
            number += 1
        return f"USR-{number:04d}"

    def register(self, full_name, email, password, phone, role="donor",
                 donor_type=None, organization="", actor=None, ngo_id=None):
        role = validate_choice(role, config.roles, "Role")
        if role not in config.public_roles:
            check_permission(actor, "manage_users")
        return self.create_account(role, full_name, email, password, phone,
                                   donor_type, organization, ngo_id)

    def create_account(self, role, full_name, email, password, phone,
                       donor_type=None, organization="", ngo_id=None):
        full_name = validate_name(full_name)
        email = validate_email(email)
        phone = validate_phone(phone)
        password = validate_password(password)
        if email in self.emails:
            raise DuplicateError("An account with this email already exists.")

        record = {
            "user_id": self.new_id(),
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "password": password,
            "created_at": now_text(),
            "is_active": True,
            "role": role,
        }
        if role == "donor":
            record["donor_type"] = validate_choice(donor_type or "Other", config.donor_types, "Donor type")
            record["organization"] = " ".join(str(organization or "").split())[:100]
        elif role == "ngo":
            record["ngo_id"] = str(ngo_id or "").strip()
        self.add_record(record)
        self.save()
        return create_user(record)

    def ensure_admin(self):
        for record in self.records.values():
            if record["role"] == "admin":
                return
        admin = config.default_admin
        self.create_account("admin", admin["full_name"], admin["email"],
                            admin["password"], admin["phone"])

    def authenticate(self, email, password):
        email = str(email or "").strip().lower()
        for record in self.records.values():
            if record["email"] == email and record["password"] == str(password or ""):
                if not record["is_active"]:
                    raise AuthenticationError("This account is deactivated. Contact an administrator.")
                return create_user(record)
        raise AuthenticationError("Invalid email or password.")

    def get(self, user_id):
        user_id = validate_user_id(user_id)
        if user_id not in self.records:
            raise NotFoundError(f"User {user_id} was not found.")
        return create_user(self.records[user_id])

    def list_users(self, roles=(), is_active=None, query=""):
        needle = query.strip().lower()
        result = []
        for record in self.records.values():
            if roles and record["role"] not in roles:
                continue
            if is_active is not None and record["is_active"] != is_active:
                continue
            text = f"{record['user_id']} {record['full_name']} {record['email']}".lower()
            if needle in text:
                result.append(create_user(record))
        return result

    def count_by_role(self):
        counts = {role: 0 for role in config.roles}
        for record in self.records.values():
            counts[record["role"]] += 1
        return counts

    def set_role(self, actor, user_id, new_role, ngo_id=None):
        check_permission(actor, "manage_users")
        new_role = validate_choice(new_role, config.roles, "Role")
        user = self.get(user_id)
        if user.user_id == actor.user_id:
            raise AuthorizationError("You cannot change your own role.")
        record = self.records[user.user_id]
        if new_role == "ngo":
            linked_ngo_id = str(ngo_id or record.get("ngo_id", "")).strip()
            if not linked_ngo_id:
                raise ValidationError("Select an NGO before assigning the NGO role.")
            record["ngo_id"] = linked_ngo_id
        else:
            record.pop("ngo_id", None)
        record["role"] = new_role
        if new_role != "donor":
            record.pop("donor_type", None)
            record.pop("organization", None)
        self.save()

    def set_active(self, actor, user_id, active):
        check_permission(actor, "manage_users")
        user = self.get(user_id)
        if user.user_id == actor.user_id and not active:
            raise AuthorizationError("You cannot deactivate your own account.")
        self.records[user.user_id]["is_active"] = active
        self.save()

    def reset_password(self, actor, user_id, new_password):
        check_permission(actor, "manage_users")
        user = self.get(user_id)
        self.records[user.user_id]["password"] = validate_password(new_password)
        self.save()
