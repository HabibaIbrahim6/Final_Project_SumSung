"""Load and normalize current application data for reporting."""

from analytics.data_loader import load_live_data
from session import (
    get_allocation_service,
    get_donation_service,
    get_tracking_service,
    get_user_service,
)


def get_clean_data():
    return load_live_data(
        get_donation_service(),
        get_user_service(),
        get_allocation_service(),
        get_tracking_service(),
    )
