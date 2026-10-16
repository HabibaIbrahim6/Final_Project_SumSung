"""KPI and report calculations over normalized analytics tables."""

import pandas as pd

DONOR_REPORT_COLUMNS = [
    "donor_id",
    "donor_name",
    "donations",
    "donated_kg",
    "delivered_kg",
    "expired",
    "delivered_pct",
]
NGO_REPORT_COLUMNS = [
    "ngo_id",
    "ngo_name",
    "city",
    "distributions",
    "allocated_kg",
    "delivered_kg",
    "success_rate_pct",
    "avg_response_min",
]


def total_donated_kg(donations):
    return float(donations["quantity_kg"].sum())


def total_allocated_kg(distributions):
    active = distributions[distributions["status"] != "Cancelled"]
    return float(active["allocated_quantity_kg"].sum())


def total_delivered_kg(distributions):
    return float(distributions["delivered_quantity_kg"].sum())


def expired_count(donations):
    return int((donations["status"] == "Expired").sum())


def success_rate(distributions):
    finished = distributions[distributions["status"].isin(["Delivered", "Failed"])]
    if finished.empty:
        return 0.0
    delivered = (finished["status"] == "Delivered").sum()
    return round(float(delivered / len(finished) * 100), 1)


def avg_response_minutes(donations, distributions):
    if donations.empty or distributions.empty:
        return 0.0
    merged = distributions.merge(
        donations[["donation_id", "created_at"]], on="donation_id", how="inner"
    )
    if merged.empty:
        return 0.0
    merged = merged.sort_values("allocated_at").drop_duplicates(
        subset="donation_id", keep="first"
    )
    minutes = (merged["allocated_at"] - merged["created_at"]).dt.total_seconds() / 60
    return round(float(minutes.mean()), 1) if not minutes.empty else 0.0


def donor_impact_report(donations, distributions):
    if donations.empty:
        return pd.DataFrame(columns=DONOR_REPORT_COLUMNS)
    delivered = distributions.groupby("donation_id")["delivered_quantity_kg"].sum()
    frame = donations.copy()
    frame["delivered_kg"] = frame["donation_id"].map(delivered).fillna(0)
    frame["is_expired"] = frame["status"] == "Expired"
    report = frame.groupby(["donor_id", "donor_name"]).agg(
        donations=("donation_id", "count"),
        donated_kg=("quantity_kg", "sum"),
        delivered_kg=("delivered_kg", "sum"),
        expired=("is_expired", "sum"),
    ).reset_index()
    report["delivered_pct"] = (
        report["delivered_kg"] / report["donated_kg"] * 100
    ).round(1)
    return report.sort_values("delivered_kg", ascending=False)[DONOR_REPORT_COLUMNS]


def ngo_performance_report(donations, distributions, ngos):
    if distributions.empty:
        return pd.DataFrame(columns=NGO_REPORT_COLUMNS)
    frame = distributions.merge(
        donations[["donation_id", "created_at"]], on="donation_id", how="left"
    )
    response = (frame["allocated_at"] - frame["created_at"]).dt.total_seconds() / 60
    frame["response_min"] = response
    frame["is_delivered"] = frame["status"] == "Delivered"
    frame["is_failed"] = frame["status"] == "Failed"
    report = frame.groupby("ngo_id").agg(
        distributions=("distribution_id", "count"),
        allocated_kg=("allocated_quantity_kg", "sum"),
        delivered_kg=("delivered_quantity_kg", "sum"),
        delivered_n=("is_delivered", "sum"),
        failed_n=("is_failed", "sum"),
        avg_response_min=("response_min", "mean"),
    ).reset_index()
    report = report.merge(ngos[["ngo_id", "ngo_name", "city"]], on="ngo_id", how="left")
    finished = report["delivered_n"] + report["failed_n"]
    report["success_rate_pct"] = (
        report["delivered_n"] / finished.where(finished > 0) * 100
    ).round(1).fillna(0)
    report["avg_response_min"] = report["avg_response_min"].round(0)
    return report[NGO_REPORT_COLUMNS].sort_values("delivered_kg", ascending=False)
