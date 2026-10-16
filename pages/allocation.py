import html

import pandas as pd
import streamlit as st

import config
from algorithms.hash_table import HashTable
from algorithms.merge_sort import MergeSort
from algorithms.search import Search
from session import (
    cancel_tracking_for_reversed_allocation,
    flash,
    get_allocation_service,
    get_tracking_service,
    require_access,
    show_flashes,
)
from ui import format_minutes, hero, urgency_label
from validators import FoodRescueError


def urgency_for(item):
    if item["status"] != "Pending":
        return "-"
    return urgency_label(item["minutes_to_expiry"])


def items_table(items):
    return pd.DataFrame([
        {"Batch": i["ref"], "Food": i["food_name"], "Category": i["food_type"],
         "Quantity": f'{i["quantity"]:g} {i["unit"]}',
         "Time left": format_minutes(i["minutes_to_expiry"]),
         "Urgency": urgency_for(i), "Status": i["status"], "City": i["donor_location"]}
        for i in items
    ])


def explorer_page():
    require_access("view_all_donations")
    allocation = get_allocation_service()
    show_flashes()
    hero("Donations Explorer", "Prioritise donations by expiry and look up any batch instantly.")

    items = allocation.all_items()
    if not items:
        st.info("No donations hyet.")
        return

    pending = [i for i in items if i["status"] == "Pending"]
    critical = [i for i in pending if i["minutes_to_expiry"] <= 720]
    average = sum(i["minutes_to_expiry"] for i in pending) // len(pending) if pending else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total donations", len(items))
    k2.metric("Pending", len(pending))
    k3.metric("Critical (12h or less)", len(critical))
    k4.metric("Avg time left", format_minutes(average) if pending else "-")

    st.write("")
    tab1, tab2, tab3 = st.tabs(["Prioritised dispatch", "Batch finder", "Overview"])

    with tab1:
        left, right = st.columns([1, 3], gap="large")
        with left:
            strategy = st.radio("Dispatch strategy", ["Most urgent first", "Least urgent first"])
            status_filter = st.selectbox("Status", ["All"] + list(config.statuses))
        rows = list(items)
        if status_filter != "All":
            rows = Search().find_by_status(items, status_filter)
        sorter = MergeSort()
        ordered = sorter.sort(rows, reverse=(strategy == "Least urgent first"))
        with right:
            st.markdown(
                f'<span class="pill">Merge Sort</span>'
                f'<span class="pill">{sorter.comparisons} comparisons</span>'
                f'<span class="pill">{sorter.recursive_calls} recursive calls</span>',
                unsafe_allow_html=True,
            )
            if ordered:
                st.dataframe(items_table(ordered), hide_index=True, use_container_width=True)
            else:
                st.info("No donations with this status.")

    with tab2:
        st.subheader("Find a batch")
        number = st.number_input("Batch number (DON-0001 is 1)", min_value=1, value=1, step=1)
        table = HashTable(capacity=11)
        for item in items:
            table.insert(item["id"], item)
        found = table.get(int(number))
        if found:
            st.markdown(
                f"""
                <div class="result-card">
                  <h4>Batch {html.escape(found['ref'])} &nbsp; {urgency_for(found)}</h4>
                  <b>Food:</b> {html.escape(found['food_name'])} &nbsp;|&nbsp;
                  <b>Category:</b> {html.escape(found['food_type'])} &nbsp;|&nbsp;
                  <b>Quantity:</b> {found['quantity']:g} {html.escape(found['unit'])} &nbsp;|&nbsp;
                  <b>Time left:</b> {format_minutes(found['minutes_to_expiry'])} &nbsp;|&nbsp;
                  <b>City:</b> {html.escape(found['donor_location'])} &nbsp;|&nbsp;
                  <b>Status:</b> {html.escape(found['status'])}
                </div>
                """,
                unsafe_allow_html=True,
            )
            if found["status"] == "Pending":
                if found["minutes_to_expiry"] <= 720:
                    st.warning("Dispatch immediately: this batch expires within 12 hours.")
                elif found["minutes_to_expiry"] <= 2880:
                    st.info("Schedule pickup soon.")
                else:
                    st.success("No urgency, plenty of time left.")
        else:
            st.error("No batch found with this number.")

    with tab3:
        st.subheader("Hours left per pending batch")
        if pending:
            chart = pd.DataFrame(
                {"Hours left": [round(i["minutes_to_expiry"] / 60, 1) for i in pending]},
                index=[f'{i["ref"]} {i["food_name"]}' for i in pending],
            )
            st.bar_chart(chart)
        else:
            st.info("No pending donations.")
        st.subheader("All donations")
        st.dataframe(items_table(items), hide_index=True, use_container_width=True)


def smart_allocation_page():
    user = require_access("manage_allocations")
    allocation = get_allocation_service()
    show_flashes()
    hero("Smart Allocation Center",
         "The most urgent donation first, matched to the best NGO with clear reasons.")

    pending = allocation.get_pending_queue()
    waiting = len(allocation.open_proposals())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Donations in queue", len(pending))
    k2.metric("Partner NGOs", len(allocation.ngos))
    k3.metric("Most urgent", format_minutes(pending[0]["minutes_to_expiry"]) if pending else "-")
    k4.metric("Waiting for admin", waiting)
    st.write("")

    if not pending:
        st.success("No pending donations. Everything is allocated.")
        return

    left, right = st.columns([2, 3], gap="large")

    with left:
        st.subheader("Pending queue")
        st.dataframe(
            pd.DataFrame([
                {"Batch": d["ref"], "Food": d["food_name"],
                 "Quantity": f'{d["quantity"]:g} {d["unit"]}',
                 "Time left": format_minutes(d["minutes_to_expiry"]),
                 "Urgency": urgency_label(d["minutes_to_expiry"])}
                for d in pending
            ]),
            hide_index=True,
            use_container_width=True,
        )
        labels = {f'{d["ref"]} - {d["food_name"]} - {format_minutes(d["minutes_to_expiry"])} left': d["ref"]
                  for d in pending}
        ref = labels[st.selectbox("Donation to allocate", list(labels))]

    with right:
        st.subheader("Recommended NGO")
        rec = allocation.recommend(ref)

        if not rec:
            st.warning("No recommendation is available for this donation.")
            return

        if rec.get("donation") is None:
            st.error("The recommendation does not contain donation data.")
            st.write("Available keys:", list(rec.keys()))
            return

        donation = rec["donation"]
        donation = rec["donation"]

        if rec["ngo"] is None:
            st.warning("No NGO can take this donation in time.")
        else:
            ngo = rec["ngo"]
            st.markdown(
                f"""
                <div class="result-card">
                  <h4>{html.escape(ngo['name'])} &nbsp; ({html.escape(ngo['location'])})</h4>
                  Pickup in about <b>{round(rec['total_minutes'])} min</b> &nbsp;|&nbsp;
                  Distance <b>{rec['distance_km']} km</b> &nbsp;|&nbsp;
                  Food expires in <b>{format_minutes(donation['minutes_to_expiry'])}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write("")
            st.markdown("**Why this NGO?**")
            for reason in rec["reasons"]:
                st.markdown(f"- {reason}")

            if allocation.has_open_proposal(ref):
                st.info("Already sent to the admin for approval.")
            elif st.button("Send to admin for approval", type="primary"):
                try:
                    allocation.propose(user, ref)
                except FoodRescueError as error:
                    st.error(str(error))
                else:
                    flash("success", f"{ref} was sent to the admin for approval.")
                    st.rerun()

        if rec["ranked"]:
            st.markdown("**All eligible NGOs (best first)**")
            st.dataframe(
                pd.DataFrame([
                    {"NGO": c["ngo"]["name"], "Distance (km)": c["distance_km"],
                     "Pickup time (min)": round(c["total_minutes"])}
                    for c in rec["ranked"]
                ]),
                hide_index=True,
                use_container_width=True,
            )
        if rec["rejected"]:
            with st.expander(f"NGOs that were ruled out ({len(rec['rejected'])})"):
                for r in rec["rejected"]:
                    st.markdown(f"- **{r['ngo']['name']}** {r['reason']}")

    st.divider()
    st.subheader("Smart allocation vs. simple allocation")
    comparison = allocation.compare_with_baseline()
    g, b = comparison["greedy"], comparison["baseline"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Avg pickup time", f"{g['avg_minutes']} min",
              delta=f"{round(g['avg_minutes'] - b['avg_minutes'], 1)} min vs simple", delta_color="inverse")
    m2.metric("Total distance", f"{g['total_km']} km",
              delta=f"{round(g['total_km'] - b['total_km'], 1)} km vs simple", delta_color="inverse")
    m3.metric("Donations placed", f"{g['allocated']} / {g['allocated'] + g['unallocated']}",
              delta=f"{g['allocated'] - b['allocated']} vs simple")
    st.caption("Simple means giving each donation to the first NGO in the list that can take it.")

    with st.expander("Algorithm details"):
        st.write(f"Comparisons for this recommendation: **{rec['comparisons']}**")
        st.write(f"Heap comparisons in the priority queue so far: **{allocation.queue.comparisons}**")
        st.write("Queue: min-heap by time to expiry. Ranking: manual merge sort. "
                 "Allocation: greedy by smallest total pickup time.")
        st.write("Limitations: greedy has no look-ahead, so an urgent donation can use capacity a later "
                 "donation needed. A donation is never split between NGOs. Travel time is estimated "
                 "from distance only.")


def admin_allocations_page():
    admin = require_access("approve_allocations")
    allocation = get_allocation_service()
    show_flashes()
    hero("Allocation Review", "Check each proposed allocation and its reasons before confirming it.")

    waiting = allocation.open_proposals()
    k1, k2, k3 = st.columns(3)
    k1.metric("Waiting for review", len(waiting))
    k2.metric("Approved", allocation.count_proposals("Approved"))
    k3.metric("Rejected", allocation.count_proposals("Rejected"))
    st.write("")

    tab1, tab2, tab3 = st.tabs(["Review proposals", "History and undo", "NGO capacity"])

    with tab1:
        if not waiting:
            st.info("No proposals waiting. Coordinators send them from the Smart Allocation page.")
        for proposal in waiting:
            ref = proposal["ref"]
            item = allocation.find_item(ref)
            ngo = allocation.ngo_by_id(proposal["ngo_id"])
            st.markdown(
                f"""
                <div class="proposal-card">
                  <b>{html.escape(ref)}</b> - {html.escape(item['food_name'])} -
                  {item['quantity']:g} {html.escape(item['unit'])} - {html.escape(item['donor_location'])}
                  &nbsp; {urgency_label(item['minutes_to_expiry'])}<br>
                  Proposed NGO: <b>{html.escape(ngo['name'])}</b> ({html.escape(ngo['location'])}),
                  pickup in about {round(proposal['total_minutes'])} min,
                  proposed by {html.escape(proposal['proposed_by'])}
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Why was this NGO chosen?"):
                for reason in proposal["reasons"]:
                    st.markdown(f"- {reason}")
            col1, col2, _ = st.columns([1, 1, 4])
            if col1.button("Approve", key="approve_" + ref, type="primary"):
                try:
                    allocation.approve(admin, ref)
                except FoodRescueError as error:
                    st.error(str(error))
                else:
                    get_tracking_service()
                    flash("success", f"{ref} allocated to {ngo['name']}.")
                    st.rerun()
            if col2.button("Reject", key="reject_" + ref):
                try:
                    allocation.reject(admin, ref)
                except FoodRescueError as error:
                    st.error(str(error))
                else:
                    flash("info", f"Proposal for {ref} was rejected.")
                    st.rerun()
            st.write("")

    with tab2:
        rows = allocation.history_rows()
        if not rows:
            st.info("No confirmed allocations yet.")
        else:
            st.dataframe(
                pd.DataFrame([{"Batch": r["ref"], "NGO": r["ngo"], "Quantity": r["quantity"]} for r in rows]),
                hide_index=True,
                use_container_width=True,
            )
            if st.button("Undo last allocation"):
                try:
                    last = allocation.undo_last(admin)
                    cancel_tracking_for_reversed_allocation(last["ref"])
                except FoodRescueError as error:
                    st.error(str(error))
                else:
                    flash("success", f"Allocation of {last['ref']} was undone.")
                    st.rerun()

    with tab3:
        st.dataframe(
            pd.DataFrame([
                {"NGO": n["name"], "Location": n["location"],
                 "Accepts": ", ".join(n["accepted_food_types"]),
                 "Remaining capacity": ", ".join(f"{v:g} {k}" for k, v in n["remaining_capacity"].items()),
                 "Pickup prep (min)": n["pickup_time_minutes"]}
                for n in allocation.ngos
            ]),
            hide_index=True,
            use_container_width=True,
        )
