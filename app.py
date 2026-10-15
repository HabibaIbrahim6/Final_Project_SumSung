import streamlit as st

import allocation_pages
import donation_pages
import NGO_pages
import user_pages
from session import get_current_user, logout
from ui import ICON, LOGO, inject_css

page_registry = {
    "create_donation": ("Create Donation", donation_pages.create_donation_page),
    "my_donations": ("My Donations", donation_pages.my_donations_page),
    "explorer": ("Donations Explorer", allocation_pages.explorer_page),
    "smart_allocation": ("Smart Allocation", allocation_pages.smart_allocation_page),
    "admin_allocations": ("Admin: Allocations", allocation_pages.admin_allocations_page),
    "admin_users": ("Admin: User Management", user_pages.admin_users_page),
    "admin_ngos": ("Admin: NGO Management", NGO_pages.admin_ngos_page),
    "ngo_dashboard": ("NGO Dashboard", NGO_pages.ngo_dashboard_page),
    "ngo_profile": ("NGO Profile", NGO_pages.ngo_profile_page),
}


def build_navigation(user):
    if user is None:
        login_page = st.Page(user_pages.login_register_page, title="Login / Register",
                             url_path="login", default=True)
        return st.navigation([login_page])

    pages = []
    for key in user.pages:
        if key not in page_registry:
            continue
        title, function = page_registry[key]
        if key == "my_donations" and user.can("view_all_donations"):
            title = "All Donations"
        pages.append(st.Page(function, title=title, url_path=key))
    if not pages:
        pages.append(st.Page(user_pages.login_register_page, title="Home", url_path="home"))

    with st.sidebar:
        st.write(user.welcome_message())
        st.caption(user.email)
        st.button("Log out", on_click=logout)
    return st.navigation(pages)


def main():
    st.set_page_config(page_title="Food Rescue Coordinator", page_icon=str(ICON), layout="wide")
    st.logo(str(LOGO), icon_image=str(ICON))
    inject_css()
    build_navigation(get_current_user()).run()


main()
