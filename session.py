import streamlit as st

from services.allocation_service import AllocationService
from services.donation_service import DonationService
from services.distribution import DELIVERED, IN_TRANSIT
from services.tracking_service import TrackingService
from services.user_service import UserService
from validators import FoodRescueError


@st.cache_resource
def get_user_service():
    return UserService()


@st.cache_resource
def get_donation_service():
    return DonationService()


@st.cache_resource
def get_allocation_service():
    return AllocationService(get_donation_service())


@st.cache_resource
def _create_tracking_service():
    return TrackingService(auto_save=True)


def get_tracking_service():
    tracking = _create_tracking_service()
    sync_tracking_data(tracking, get_donation_service(), get_allocation_service())
    return tracking


def sync_tracking_data(tracking, donation_service, allocation):
    donations = donation_service.all_donations()
    for donation in donations:
        if donation.unit == "kg":
            tracking.register_donation(donation.donation_id, donation.quantity)

    records = tracking.list_distributions()
    assigned = [
        donation
        for donation in donations
        if donation.unit == "kg" and donation.status in ("Allocated", "Delivered")
    ]

    def has_current_distribution(donation):
        for record in records:
            if record.donation_id != donation.donation_id or record.ngo_id != str(donation.ngo_id):
                continue
            if record.status in ("proposed", "confirmed", "in_transit"):
                return True
            if donation.status == "Delivered" and record.status == DELIVERED:
                return True
        return False

    tracked_ids = {
        donation.donation_id for donation in assigned if has_current_distribution(donation)
    }
    for ngo in allocation.ngos:
        ngo_id = str(ngo["id"])
        reserved = sum(
            record.reserved_kg for record in records if record.ngo_id == ngo_id
        )
        untracked_allocations = sum(
            donation.quantity
            for donation in assigned
            if str(donation.ngo_id) == ngo_id and donation.donation_id not in tracked_ids
        )
        remaining = float(ngo["remaining_capacity"].get("kg", 0))
        tracking.register_ngo(ngo_id, remaining + reserved + untracked_allocations)

    for donation in assigned:
        if donation.donation_id in tracked_ids:
            record = next(
                record
                for record in records
                if record.donation_id == donation.donation_id
                and record.ngo_id == str(donation.ngo_id)
                and (
                    record.status in ("proposed", "confirmed", "in_transit")
                    or (donation.status == "Delivered" and record.status == DELIVERED)
                )
            )
        else:
            record = tracking.import_allocation(
                donation.donation_id,
                donation.ngo_id,
                donation.quantity,
                delivered=donation.status == "Delivered",
            )
        if donation.status == "Delivered" and record.status != DELIVERED:
            if record.status == "proposed":
                record = tracking.confirm(record.distribution_id)
            if record.status == "confirmed":
                record = tracking.start_transit(record.distribution_id)
            if record.status == IN_TRANSIT:
                tracking.mark_delivered(
                    record.distribution_id, donation.quantity
                )
    return tracking


def cancel_tracking_for_reversed_allocation(donation_id):
    tracking = get_tracking_service()
    for record in tracking.list_distributions(donation_ids=[donation_id]):
        if record.can_transition_to("cancelled"):
            tracking.cancel(record.distribution_id, "Allocation was undone by an administrator.")


def login(user):
    st.session_state["current_user_id"] = user.user_id


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def get_current_user():
    user_id = st.session_state.get("current_user_id")
    if not user_id:
        return None
    try:
        user = get_user_service().get(user_id)
    except FoodRescueError:
        logout()
        return None
    if not user.is_active:
        logout()
        return None
    return user


def require_access(*permissions):
    user = get_current_user()
    if user is None:
        st.warning("Please log in to continue.")
        st.stop()
    assert user is not None
    if not any(user.can(permission) for permission in permissions):
        st.error("Your role is not allowed to open this page.")
        st.stop()
    return user


def flash(kind, message):
    st.session_state.setdefault("flash", []).append((kind, message))


def show_flashes():
    for kind, message in st.session_state.pop("flash", []):
        getattr(st, kind)(message)
