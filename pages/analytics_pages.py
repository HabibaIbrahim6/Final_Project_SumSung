"""Impact analytics and role-scoped CSV reports."""

import streamlit as st

from analytics.access import scope_data
from analytics.data_cleaning import get_clean_data
from analytics.metrics import (
    avg_response_minutes,
    donor_impact_report,
    expired_count,
    ngo_performance_report,
    success_rate,
    total_allocated_kg,
    total_delivered_kg,
    total_donated_kg,
)
from session import require_access


def analytics_page():
    require_access("view_analytics")
    data = get_clean_data()
    donations = data["donations"]
    distributions = data["distributions"]
    ngos = data["ngos"]
    st.title("Impact Analytics")
    st.caption("Live application records; quantities are shown only for donations recorded in kg.")
    if donations.empty:
        st.info("There are no kilogram-based donations to analyze yet.")
        return

    dates = donations["created_at"].dropna().dt.date
    if dates.empty:
        st.info("There are no donations with a valid creation date.")
        return
    date_range = st.sidebar.date_input(
        "Donation date range",
        value=(dates.min(), dates.max()),
        min_value=dates.min(),
        max_value=dates.max(),
    )
    food_types = sorted(donations["food_type"].dropna().unique())
    selected_foods = st.sidebar.multiselect("Food type", food_types, default=food_types)
    donor_names = sorted(donations["donor_name"].dropna().unique())
    selected_donors = st.sidebar.multiselect("Donor", donor_names, default=donor_names)
    linked_ngo_ids = distributions["ngo_id"].dropna().astype(str).unique()
    ngo_names = ngos[ngos["ngo_id"].isin(linked_ngo_ids)]["ngo_name"].sort_values().tolist()
    selected_ngos = st.sidebar.multiselect("NGO", ngo_names, default=ngo_names)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        donations = donations[
            donations["created_at"].dt.date.between(start, end)
        ]
    donations = donations[
        donations["food_type"].isin(selected_foods)
        & donations["donor_name"].isin(selected_donors)
    ]
    distributions = distributions[
        distributions["donation_id"].isin(donations["donation_id"])
    ]
    selected_ngo_ids = ngos.loc[ngos["ngo_name"].isin(selected_ngos), "ngo_id"]
    distributions = distributions[distributions["ngo_id"].isin(selected_ngo_ids)]

    metrics = st.columns(6)
    metrics[0].metric("Donated", f"{total_donated_kg(donations):,.1f} kg")
    metrics[1].metric("Allocated", f"{total_allocated_kg(distributions):,.1f} kg")
    metrics[2].metric("Delivered", f"{total_delivered_kg(distributions):,.1f} kg")
    metrics[3].metric("Expired", expired_count(donations))
    metrics[4].metric("Success rate", f"{success_rate(distributions):.1f}%")
    metrics[5].metric("Avg. response", f"{avg_response_minutes(donations, distributions):.1f} min")

    st.subheader("Donations by month")
    monthly = donations.groupby(donations["created_at"].dt.strftime("%Y-%m"))[
        "quantity_kg"
    ].sum()
    st.bar_chart(monthly)
    left, right = st.columns(2)
    with left:
        st.subheader("Donations by food type (kg)")
        st.bar_chart(donations.groupby("food_type")["quantity_kg"].sum().sort_values())
    with right:
        st.subheader("Expiry rate by food type")
        expired_rate = (
            donations["status"].eq("Expired").groupby(donations["food_type"]).mean() * 100
        )
        st.bar_chart(expired_rate)
    st.subheader("Current NGO remaining capacity")
    st.dataframe(
        {
            "NGO": ngos["ngo_name"],
            "City": ngos["city"],
            "Remaining capacity (kg)": ngos["capacity_kg_per_day"],
        },
        hide_index=True,
        use_container_width=True,
    )


def reports_page():
    user = require_access(
        "view_own_donations", "view_eligible_donations", "view_all_donations"
    )
    data = get_clean_data()
    donations, distributions = scope_data(
        data["donations"],
        data["distributions"],
        user.role,
        user.user_id,
        getattr(user, "ngo_id", None),
    )
    ngos = data["ngos"]
    if user.role == "ngo":
        ngos = ngos[ngos["ngo_id"] == str(user.ngo_id)]

    st.title("Impact Reports")
    st.caption("Reports include only kilogram-based donation records.")
    if user.role == "donor":
        donor_report = donor_impact_report(donations, distributions)
        _show_report(
            "Your donation impact",
            donor_report,
            f"donor-impact-{user.user_id}.csv",
        )
    elif user.role == "ngo":
        ngo_report = ngo_performance_report(donations, distributions, ngos)
        _show_report(
            "Your NGO performance",
            ngo_report,
            f"ngo-performance-{user.ngo_id or 'unlinked'}.csv",
        )
    else:
        donor_report = donor_impact_report(donations, distributions)
        ngo_report = ngo_performance_report(donations, distributions, ngos)
        _show_report("Donor impact", donor_report, "donor-impact.csv")
        _show_report("NGO performance", ngo_report, "ngo-performance.csv")


def _show_report(title, report, file_name):
    st.subheader(title)
    st.dataframe(report, hide_index=True, use_container_width=True)
    st.download_button(
        f"Download {title.lower()} CSV",
        data=report.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
    )
