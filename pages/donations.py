from datetime import date, datetime, time, timedelta

import streamlit as st

import config
from session import flash, get_donation_service, get_user_service, require_access, show_flashes
from ui import hero
from validators import FoodRescueError


def create_donation_page():
    user = require_access("create_donation")
    donations = get_donation_service()
    show_flashes()

    hero("Create a Donation", "Describe the surplus food. It will be checked and queued for allocation to an NGO.")

    today = date.today()
    count = st.session_state.get("form_count", 0)
    with st.form("create_donation_" + str(count)):
        col1, col2 = st.columns(2)
        
        food_name = col1.text_input("Food name", placeholder="e.g. Chicken and rice meals")
        category = col2.selectbox("Category", config.food_categories)
        quantity = col1.number_input("Quantity", min_value=0.0, value=1.0, step=0.5)
        unit = col2.selectbox("Unit", config.units)
        expiry = col1.date_input("Expiry date", value=today + timedelta(days=1), min_value=today)
        city = col2.selectbox("City", config.cities)
        location = st.text_input("Pickup location / address")
        time_col1, time_col2 = st.columns(2)
        pickup_from = time_col1.time_input("Pickup available from", value=time(9, 0), step=900)
        pickup_until = time_col2.time_input("Pickup available until", value=time(17, 0), step=900)
        notes = st.text_area("Notes (allergens, storage, packaging)", max_chars=300)
        submitted = st.form_submit_button("Submit donation", type="primary")

    if submitted:
        try:
            donation = donations.create(
                user, food_name, category, quantity, unit, expiry, city, location,
                pickup_from.strftime("%H:%M"), pickup_until.strftime("%H:%M"), notes)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", f"Donation {donation.donation_id} submitted with status {donation.status}.")
            st.session_state["form_count"] = count + 1
            st.rerun()


def my_donations_page():
    user = require_access("view_own_donations", "view_all_donations")
    donations = get_donation_service()
    show_flashes()
    donations.expire_overdue()

    sees_all = user.can("view_all_donations")
    hero("All Donations" if sees_all else "My Donations", "Track every donation and its status.")

    visible = donations.list_visible(user)
    if not visible:
        st.info("No donations yet.")
        return

    counts = donations.status_counts(visible)
    columns = st.columns(len(config.statuses) + 1)
    columns[0].metric("Total", len(visible))
    for column, status in zip(columns[1:], config.statuses):
        column.metric(status, counts[status])

    filtered = filter_donations(visible)
    show_table(filtered, sees_all)
    st.divider()
    show_manage(user, donations, filtered)


def filter_donations(visible):
    col1, col2, col3 = st.columns([2, 2, 3])
    statuses = col1.multiselect("Status", config.statuses)
    categories = col2.multiselect("Category", config.food_categories)
    text = col3.text_input("Search", placeholder="ID, food name, category or location")
    result = []
    for donation in visible:
        if statuses and donation.status not in statuses:
            continue
        if categories and donation.category not in categories:
            continue
        if not donation.matches(text):
            continue
        result.append(donation)
    return result[::-1]


def show_table(filtered, sees_all):
    if not filtered:
        st.warning("No donations match the current filters.")
        return
    users = get_user_service()
    rows = []
    for d in filtered:
        row = {"ID": d.donation_id, "Food": d.food_name, "Category": d.category,
               "Quantity": f"{d.quantity:g} {d.unit}", "Expiry": d.expiry_date.isoformat(),
               "City": d.city, "Pickup window": f"{d.pickup_from} - {d.pickup_until}", "Status": d.status,
               "Created": d.created_at}
        if sees_all:
            try:
                row["Donor"] = users.get(d.donor_id).full_name
            except FoodRescueError:
                row["Donor"] = d.donor_id
        rows.append(row)
    st.dataframe(rows, hide_index=True)


def can_edit(user, donation):
    return (donation.is_pending() and donation.donor_id == user.user_id
            and user.can("edit_own_donation"))


def can_cancel(user, donation):
    if not donation.is_pending():
        return False
    if user.can("cancel_any_donation"):
        return True
    return donation.donor_id == user.user_id and user.can("cancel_own_donation")


def show_manage(user, donations, filtered):
    st.subheader("Manage a donation")
    options = {}
    for d in filtered:
        if can_edit(user, d) or can_cancel(user, d):
            options[f"{d.donation_id} - {d.food_name} ({d.status})"] = d
    if not options:
        st.caption("Nothing to manage right now. Only Pending donations can be edited or cancelled.")
        return

    donation = options[st.selectbox("Select a donation", list(options))]
    st.caption(f"Expires in {donation.days_to_expiry()} day(s) on {donation.expiry_date.isoformat()}")

    edit_tab, cancel_tab = st.tabs(["Edit", "Cancel"])
    with edit_tab:
        if can_edit(user, donation):
            show_edit_form(user, donations, donation)
        else:
            st.info("You cannot edit this donation.")
    with cancel_tab:
        if can_cancel(user, donation):
            show_cancel_form(user, donations, donation)
        else:
            st.info("You cannot cancel this donation.")


def index_of(options, value):
    if value in options:
        return options.index(value)
    return 0


def show_edit_form(user, donations, donation):
    start = datetime.strptime(donation.pickup_from, "%H:%M").time()
    end = datetime.strptime(donation.pickup_until, "%H:%M").time()
    with st.form("edit_form_" + donation.donation_id):
        col1, col2 = st.columns(2)
        food_name = col1.text_input("Food name", value=donation.food_name)
        category = col2.selectbox("Category", config.food_categories,
                                  index=index_of(config.food_categories, donation.category))
        quantity = col1.number_input("Quantity", min_value=0.0, value=float(donation.quantity), step=0.5)
        unit = col2.selectbox("Unit", config.units, index=index_of(config.units, donation.unit))
        expiry = col1.date_input("Expiry date", value=donation.expiry_date, min_value=date.today())
        city = col2.selectbox("City", config.cities, index=index_of(config.cities, donation.city))
        location = st.text_input("Pickup location", value=donation.pickup_location)
        time_col1, time_col2 = st.columns(2)
        pickup_from = time_col1.time_input("Pickup from", value=start, step=900)
        pickup_until = time_col2.time_input("Pickup until", value=end, step=900)
        notes = st.text_area("Notes", value=donation.notes, max_chars=300)
        submitted = st.form_submit_button("Save changes", type="primary")
    if submitted:
        try:
            donations.edit(user, donation.donation_id, food_name, category, quantity, unit,
                           expiry, city, location, pickup_from.strftime("%H:%M"),
                           pickup_until.strftime("%H:%M"), notes)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", f"Donation {donation.donation_id} updated.")
            st.rerun()


def show_cancel_form(user, donations, donation):
    with st.form("cancel_form_" + donation.donation_id):
        reason = st.selectbox("Reason", config.cancel_reasons)
        details = st.text_input("Details (required when the reason is Other)", max_chars=150)
        confirmed = st.checkbox("I understand this cannot be undone")
        submitted = st.form_submit_button("Cancel donation")
    if submitted:
        if not confirmed:
            st.error("Please tick the confirmation box first.")
            return
        if reason == "Other" and details.strip() == "":
            st.error("Please describe the reason when choosing Other.")
            return
        full_reason = reason
        if details.strip():
            full_reason = reason + ": " + details.strip()
        try:
            donations.cancel(user, donation.donation_id, full_reason)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", f"Donation {donation.donation_id} cancelled.")
            st.rerun()
