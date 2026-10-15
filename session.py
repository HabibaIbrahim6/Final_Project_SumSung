import streamlit as st

from allocation_service import AllocationService
from donation_service import DonationService
from user_service import UserService
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
