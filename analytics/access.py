"""Role-based data scoping for impact reports."""

ADMIN = "admin"
DONOR = "donor"
NGO = "ngo"


def scope_data(donations, distributions, role, user_id, ngo_id=None):
    if role == DONOR:
        donations = donations[donations["donor_id"] == user_id]
        distributions = distributions[
            distributions["donation_id"].isin(donations["donation_id"])
        ]
    elif role == NGO:
        distributions = distributions[distributions["ngo_id"] == str(ngo_id or "")]
        donations = donations[
            donations["donation_id"].isin(distributions["donation_id"])
        ]
    elif role not in (ADMIN, "coordinator"):
        donations = donations.iloc[0:0]
        distributions = distributions.iloc[0:0]
    return donations, distributions
