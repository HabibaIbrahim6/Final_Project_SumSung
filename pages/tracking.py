"""Distribution tracking for NGOs and administrator monitoring."""

import streamlit as st

from services.distribution import (
    CANCELLED,
    CONFIRMED,
    DELIVERED,
    FAILED,
    IN_TRANSIT,
    PROPOSED,
    DistributionError,
)
from session import (
    flash,
    get_allocation_service,
    get_donation_service,
    get_tracking_service,
    require_access,
    show_flashes,
)
from validators import FoodRescueError


def _distribution_rows(records, allocation):
    donations = get_donation_service()
    ngo_names = {str(ngo["id"]): ngo["name"] for ngo in allocation.ngos}
    rows = []
    for record in records:
        donation = donations.records.get(record.donation_id)
        rows.append(
            {
                "Distribution": record.distribution_id,
                "Donation": record.donation_id,
                "Food": donation.food_name if donation else "Unknown",
                "NGO": ngo_names.get(record.ngo_id, record.ngo_id),
                "Allocated (kg)": record.allocated_quantity_kg,
                "Delivered (kg)": record.delivered_quantity_kg,
                "Status": record.status.replace("_", " ").title(),
                "Last updated": record.last_change_at,
            }
        )
    return rows


def tracking_page():
    user = require_access("respond_to_offers", "manage_distribution")
    tracking = get_tracking_service()
    allocation = get_allocation_service()
    show_flashes()
    st.title("Delivery Tracking")
    records = tracking.list_distributions()
    if user.role == "ngo":
        if not user.ngo_id:
            st.info("Your account is not linked to an NGO yet.")
            return
        records = [record for record in records if record.ngo_id == user.ngo_id]
    if not records:
        st.info("There are no kilogram-based distributions to track.")
        return

    st.dataframe(
        _distribution_rows(records, allocation),
        hide_index=True,
        use_container_width=True,
    )
    options = {
        f"{record.distribution_id} · {record.donation_id} · {record.status}": record
        for record in records
    }
    selected = options[st.selectbox("Select a distribution", list(options))]
    if selected.status == CONFIRMED and st.button("Start transit"):
        try:
            tracking.start_transit(selected.distribution_id)
        except DistributionError as error:
            st.error(str(error))
        else:
            flash("success", f"{selected.distribution_id} is now in transit.")
            st.rerun()
    elif selected.status == IN_TRANSIT:
        donation = get_donation_service().get(selected.donation_id)
        quantity = st.number_input(
            "Delivered quantity (kg)",
            min_value=0.001,
            max_value=float(selected.allocated_quantity_kg),
            value=float(selected.allocated_quantity_kg),
            step=0.5,
        )
        if st.button("Mark delivered", type="primary"):
            try:
                if donation.status != "Allocated" or str(donation.ngo_id) != user.ngo_id:
                    raise FoodRescueError(
                        "The donation assignment changed; refresh before recording delivery."
                    )
                allocation.ngo_for_user(user)
                tracking.mark_delivered(selected.distribution_id, quantity)
                allocation.mark_delivered(user, donation.donation_id)
            except (DistributionError, FoodRescueError) as error:
                st.error(str(error))
            else:
                flash("success", f"{selected.distribution_id} delivery was recorded.")
                st.rerun()


def admin_distributions_page():
    admin = require_access("approve_allocations")
    tracking = get_tracking_service()
    allocation = get_allocation_service()
    donations = get_donation_service()
    show_flashes()
    st.title("Distribution Administration")
    st.caption("Manage the approved kg-based allocations and their delivery lifecycle.")
    records = tracking.list_distributions()
    summary = tracking.summarize(records)
    columns = st.columns(4)
    columns[0].metric("Distributions", summary["total"])
    columns[1].metric("Allocated", f'{summary["allocated_kg"]:,.1f} kg')
    columns[2].metric("Delivered", f'{summary["delivered_kg"]:,.1f} kg')
    columns[3].metric("Success rate", f'{summary["success_rate"] * 100:.1f}%')
    if not records:
        st.info("No kilogram-based distributions are available yet.")
    else:
        st.dataframe(
            _distribution_rows(records, allocation),
            hide_index=True,
            use_container_width=True,
        )
        choices = {
            f"{record.distribution_id} · {record.donation_id} · {record.status}": record
            for record in records
        }
        selected = choices[st.selectbox("Manage a distribution", list(choices))]
        _render_admin_actions(admin, selected, tracking, allocation, donations)

    last_action = tracking.last_action_description()
    if last_action:
        st.caption(f"Most recent action: {last_action}")
        if st.button("Undo last distribution action"):
            _undo_last(tracking, allocation, donations)


def _render_admin_actions(admin, record, tracking, allocation, donations):
    if record.status == PROPOSED and st.button("Confirm allocation"):
        _run_action(
            lambda: tracking.confirm(record.distribution_id),
            f"{record.distribution_id} was confirmed.",
        )
    elif record.status == CONFIRMED and st.button("Start transit"):
        _run_action(
            lambda: tracking.start_transit(record.distribution_id),
            f"{record.distribution_id} is now in transit.",
        )
    elif record.status == IN_TRANSIT:
        quantity = st.number_input(
            "Delivered quantity (kg)",
            min_value=0.001,
            max_value=float(record.allocated_quantity_kg),
            value=float(record.allocated_quantity_kg),
            step=0.5,
            key=f"admin-delivered-{record.distribution_id}",
        )
        if st.button("Mark delivered", type="primary"):
            try:
                if donations.get(record.donation_id).status != "Allocated":
                    raise FoodRescueError(
                        "The donation assignment changed; refresh before recording delivery."
                    )
                tracking.mark_delivered(record.distribution_id, quantity)
                donations.set_status(record.donation_id, "Delivered")
            except (DistributionError, FoodRescueError) as error:
                st.error(str(error))
            else:
                flash("success", f"{record.distribution_id} delivery was recorded.")
                st.rerun()

    if record.status in (PROPOSED, CONFIRMED, IN_TRANSIT):
        reason = st.text_input(
            "Reason for cancellation or failure",
            key=f"reason-{record.distribution_id}",
        )
        cancel_allowed = record.status in (PROPOSED, CONFIRMED)
        col_cancel, col_fail = st.columns(2)
        if cancel_allowed and col_cancel.button("Cancel distribution"):
            _release_distribution(
                admin, record, tracking, allocation, CANCELLED, reason
            )
        if record.status == IN_TRANSIT and col_fail.button("Mark failed"):
            _release_distribution(admin, record, tracking, allocation, FAILED, reason)


def _release_distribution(admin, record, tracking, allocation, final_status, reason):
    try:
        if not reason.strip():
            raise DistributionError("A reason is required.")
        if allocation.donation_service.get(record.donation_id).status != "Allocated":
            raise DistributionError(
                "The donation is no longer allocated; refresh the page before changing its distribution."
            )
        if final_status == CANCELLED:
            tracking.cancel(record.distribution_id, reason)
        else:
            tracking.fail(record.distribution_id, reason)
        allocation.release_assignment(admin, record.donation_id)
    except (DistributionError, FoodRescueError) as error:
        st.error(str(error))
    else:
        flash("info", f"{record.distribution_id} was {final_status}. The donation returned to Pending.")
        st.rerun()


def _undo_last(tracking, allocation, donations):
    try:
        action = tracking.history_entries()[0]
        record = tracking.get(action["distribution_id"])
        previous_status = record.status
        tracking.undo_last()
        if action["action"] == "create":
            flash("success", f"Undid the creation of {record.distribution_id}.")
            st.rerun()
        restored = tracking.get(record.distribution_id)
        donation = donations.get(record.donation_id)
        if previous_status == DELIVERED and donation.status == "Delivered":
            donations.set_status(record.donation_id, "Allocated", record.ngo_id)
        elif previous_status in (CANCELLED, FAILED) and donation.status == "Pending":
            allocation.confirm(record.donation_id, record.ngo_id)
    except (DistributionError, FoodRescueError, ValueError) as error:
        st.error(str(error))
    else:
        flash("success", f"Undid the last action for {restored.distribution_id}.")
        st.rerun()


def _run_action(action, success_message):
    try:
        action()
    except DistributionError as error:
        st.error(str(error))
    else:
        flash("success", success_message)
        st.rerun()
