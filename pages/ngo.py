import pandas as pd
import streamlit as st

import config
from session import (
    flash,
    get_allocation_service,
    get_user_service,
    require_access,
    show_flashes,
)
from ui import hero
from validators import FoodRescueError, InvalidStateError


def ngo_dashboard_page():
    user = require_access("view_eligible_donations")
    allocation = get_allocation_service()
    show_flashes()
    hero("NGO Dashboard", "Review eligible donations and track your assigned deliveries.")

    try:
        ngo = allocation.ngo_for_user(user)
        eligible = allocation.eligible_donations(user)
        assigned = allocation.assigned_donations(user)
    except InvalidStateError as error:
        st.info(str(error))
        return
    except FoodRescueError as error:
        st.error(str(error))
        return

    allocated = [donation for donation in assigned if donation.status == "Allocated"]
    delivered = [donation for donation in assigned if donation.status == "Delivered"]
    metrics = st.columns(4)
    metrics[0].metric("Partner NGO", ngo["name"])
    metrics[1].metric("Eligible pending donations", len(eligible))
    metrics[2].metric("Awaiting delivery", len(allocated))
    metrics[3].metric("Delivered", len(delivered))

    st.subheader("Donations matching your profile")
    st.caption("These donations match your accepted food types, remaining capacity, and estimated pickup time.")
    if eligible:
        st.dataframe(
            pd.DataFrame([
                {
                    "ID": donation.donation_id,
                    "Food": donation.food_name,
                    "Category": donation.category,
                    "Quantity": f"{donation.quantity:g} {donation.unit}",
                    "City": donation.city,
                    "Expires": donation.expiry_date.isoformat(),
                    "Pickup window": f"{donation.pickup_from} - {donation.pickup_until}",
                }
                for donation in eligible
            ]),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No pending donations currently match your NGO's profile.")

    st.divider()
    st.subheader("Assigned deliveries")
    if not assigned:
        st.info("No donations have been assigned to your NGO yet.")
        return

    for donation in assigned:
        with st.container(border=True):
            info, action = st.columns([4, 1])
            info.markdown(
                f"**{donation.donation_id} · {donation.food_name}**  \n"
                f"{donation.quantity:g} {donation.unit} · {donation.city} · "
                f"Status: **{donation.status}**"
            )
            if donation.status == "Allocated":
                action.caption("Update delivery status from the Delivery Tracking page.")


def ngo_profile_page():
    user = require_access("manage_ngo_profile")
    allocation = get_allocation_service()
    show_flashes()
    hero("NGO Profile", "Keep your location, accepted food types, and available capacity up to date.")

    try:
        ngo = allocation.ngo_for_user(user)
    except FoodRescueError as error:
        st.info(str(error))
        return

    with st.form("ngo_profile_form"):
        name = st.text_input("NGO name", value=ngo["name"])
        location = st.selectbox(
            "City",
            config.cities,
            index=config.cities.index(ngo["location"]) if ngo["location"] in config.cities else 0,
        )
        pickup_time = st.number_input(
            "Pickup preparation time (minutes)",
            min_value=0,
            value=int(ngo.get("pickup_time_minutes", 0)),
        )
        accepted_foods = st.multiselect(
            "Accepted food categories",
            options=list(config.food_categories),
            default=[food for food in ngo["accepted_food_types"] if food in config.food_categories],
        )

        st.subheader("Remaining capacity")
        capacities = {}
        columns = st.columns(len(config.units))
        for column, unit in zip(columns, config.units):
            capacities[unit] = column.number_input(
                unit,
                min_value=0.0,
                value=float(ngo["remaining_capacity"].get(unit, 0)),
                key=f"ngo_profile_capacity_{unit}",
            )
        submitted = st.form_submit_button("Save profile", type="primary")

    if submitted:
        try:
            allocation.update_ngo_profile(
                user, name, location, pickup_time, accepted_foods, capacities
            )
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", "NGO profile updated.")
            st.rerun()


def admin_ngos_page():
    admin = require_access("manage_ngos")
    allocation = get_allocation_service()
    users = get_user_service()
    show_flashes()
    hero("NGO Management", "Manage partner organizations used by eligibility and allocation.")

    with st.form("add_ngo_form"):
        name = st.text_input("NGO name")
        location = st.selectbox("City", config.cities)
        pickup_time = st.number_input("Pickup preparation time (minutes)", min_value=0, value=20)
        accepted_foods = st.multiselect(
            "Accepted food categories",
            options=list(config.food_categories),
            default=["Bakery"],
        )
        st.subheader("Remaining capacity")
        capacities = {}
        columns = st.columns(len(config.units))
        for column, unit in zip(columns, config.units):
            capacities[unit] = column.number_input(
                unit,
                min_value=0.0,
                value=100.0 if unit == "kg" else 0.0,
                key=f"new_ngo_capacity_{unit}",
            )
        submitted = st.form_submit_button("Add NGO", type="primary")

    if submitted:
        if not name.strip():
            st.error("Please enter an NGO name.")
        elif not accepted_foods:
            st.error("Select at least one accepted food category.")
        elif any(item["name"].strip().casefold() == name.strip().casefold()
                 for item in allocation.ngos):
            st.error("An NGO with this name already exists.")
        else:
            new_id = max((int(item["id"]) for item in allocation.ngos), default=0) + 1
            allocation.ngos.append({
                "id": new_id,
                "name": name.strip(),
                "location": location,
                "pickup_time_minutes": int(pickup_time),
                "accepted_food_types": accepted_foods,
                "remaining_capacity": capacities,
            })
            allocation.save_ngos()
            flash("success", f"NGO '{name.strip()}' added.")
            st.rerun()

    st.divider()
    st.subheader("Registered NGOs")
    if not allocation.ngos:
        st.info("No NGOs have been registered yet.")
        return

    linked_users = users.list_users(roles=("ngo",))
    for ngo in allocation.ngos:
        with st.expander(f"{ngo['name']} — {ngo['location']}"):
            st.write("**Accepted foods:**", ", ".join(ngo["accepted_food_types"]))
            st.write("**Remaining capacity:**")
            st.json(ngo["remaining_capacity"])
            linked = [
                user for user in linked_users
                if str(getattr(user, "ngo_id", "")) == str(ngo["id"])
            ]
            st.write(
                "**Linked representatives:**",
                ", ".join(user.full_name for user in linked) if linked else "None",
            )

            with st.form(f"edit_ngo_{ngo['id']}"):
                name = st.text_input("NGO name", value=ngo["name"])
                location = st.selectbox(
                    "City",
                    config.cities,
                    index=config.cities.index(ngo["location"]) if ngo["location"] in config.cities else 0,
                    key=f"admin_ngo_city_{ngo['id']}",
                )
                pickup_time = st.number_input(
                    "Pickup preparation time (minutes)",
                    min_value=0,
                    value=int(ngo.get("pickup_time_minutes", 0)),
                    key=f"admin_ngo_pickup_{ngo['id']}",
                )
                foods = st.multiselect(
                    "Accepted food categories",
                    options=list(config.food_categories),
                    default=[food for food in ngo["accepted_food_types"]
                             if food in config.food_categories],
                    key=f"admin_ngo_foods_{ngo['id']}",
                )
                new_capacities = {}
                columns = st.columns(len(config.units))
                for column, unit in zip(columns, config.units):
                    new_capacities[unit] = column.number_input(
                        f"{unit} capacity",
                        min_value=0.0,
                        value=float(ngo["remaining_capacity"].get(unit, 0)),
                        key=f"admin_ngo_capacity_{ngo['id']}_{unit}",
                    )
                save = st.form_submit_button("Save changes")

            if save:
                try:
                    allocation.update_ngo_profile(
                        admin, name, location, pickup_time, foods, new_capacities,
                        ngo_id=ngo["id"],
                    )
                except FoodRescueError as error:
                    st.error(str(error))
                else:
                    flash("success", f"{name.strip()} updated.")
                    st.rerun()

            if st.button("Delete NGO", key=f"delete_ngo_{ngo['id']}"):
                assigned = any(
                    str(donation.ngo_id) == str(ngo["id"])
                    and donation.status in ("Allocated", "Delivered")
                    for donation in allocation.donation_service.all_donations()
                )
                if assigned:
                    st.error("This NGO has allocated or delivered donations and cannot be deleted.")
                elif linked:
                    st.error("Unlink all NGO representatives before deleting this organization.")
                else:
                    allocation.ngos.remove(ngo)
                    allocation.save_ngos()
                    flash("success", f"{ngo['name']} deleted.")
                    st.rerun()
