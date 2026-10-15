import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from NGO_pages import ngo_dashboard_page

ngo_dashboard_page()
