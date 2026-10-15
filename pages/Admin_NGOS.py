import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from NGO_pages import admin_ngos_page

admin_ngos_page()
