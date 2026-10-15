import re
from datetime import date

import config


class FoodRescueError(Exception):
    pass


class ValidationError(FoodRescueError):
    pass


class DuplicateError(FoodRescueError):
    pass


class AuthenticationError(FoodRescueError):
    pass


class AuthorizationError(FoodRescueError):
    pass


class NotFoundError(FoodRescueError):
    pass


class InvalidStateError(FoodRescueError):
    pass


email_pattern = r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
name_pattern = r"[^\W\d_]+([ '\-][^\W\d_]+)*"
phone_pattern = r"01[0125]\d{8}"
user_id_pattern = r"USR-\d{4,}"
donation_id_pattern = r"DON-\d{4,}"
time_pattern = r"([01]\d|2[0-3]):[0-5]\d"


def clean_text(value, field, min_len=1, max_len=100):
    text = " ".join(str(value or "").split())
    if text == "":
        raise ValidationError(field + " is required.")
    if len(text) < min_len or len(text) > max_len:
        raise ValidationError(f"{field} must be between {min_len} and {max_len} characters.")
    return text


def validate_email(value):
    email = clean_text(value, "Email").lower()
    if not re.fullmatch(email_pattern, email):
        raise ValidationError("Email format is invalid (example: name@example.com).")
    return email


def validate_name(value):
    name = clean_text(value, "Full name", 2, 60)
    if not re.fullmatch(name_pattern, name):
        raise ValidationError("Full name may contain letters, spaces, hyphens and apostrophes only.")
    return name


def validate_phone(value):
    phone = re.sub(r"[\s\-]", "", str(value or ""))
    if not re.fullmatch(phone_pattern, phone):
        raise ValidationError("Phone must be 11 digits and start with 010, 011, 012 or 015.")
    return phone


def validate_password(value):
    password = str(value or "")
    if (len(password) < 8 or not re.search(r"[A-Z]", password)
            or not re.search(r"[a-z]", password) or not re.search(r"\d", password)):
        raise ValidationError("Password must be at least 8 characters with an uppercase letter, "
                              "a lowercase letter and a digit.")
    return password


def validate_user_id(value):
    text = str(value or "").strip().upper()
    if not re.fullmatch(user_id_pattern, text):
        raise ValidationError("User ID has an invalid format.")
    return text


def validate_donation_id(value):
    text = str(value or "").strip().upper()
    if not re.fullmatch(donation_id_pattern, text):
        raise ValidationError("Donation ID has an invalid format.")
    return text


def validate_choice(value, options, field):
    if value not in options:
        raise ValidationError(f"{field} must be one of: {', '.join(options)}.")
    return value


def validate_quantity(value):
    try:
        quantity = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Quantity must be a number.")
    if not quantity > 0:
        raise ValidationError("Quantity must be greater than zero.")
    if quantity > config.max_quantity:
        raise ValidationError(f"Quantity cannot exceed {config.max_quantity}.")
    return round(quantity, 2)


def validate_expiry_date(value):
    if not isinstance(value, date):
        raise ValidationError("Expiry date is required.")
    if value < date.today():
        raise ValidationError("Expiry date cannot be in the past.")
    return value


def validate_pickup_window(start, end):
    for time_text in (start, end):
        if not re.fullmatch(time_pattern, str(time_text)):
            raise ValidationError("Pickup times must use the format HH:MM.")
    if end <= start:
        raise ValidationError("Pickup end time must be after the start time.")
    return start, end
