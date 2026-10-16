users_file = "data/users.json"
donations_file = "data/donations.csv"
ngos_file = "data/ngos.json"

roles = ("donor", "ngo", "coordinator", "admin")
public_roles = ("donor", "ngo")
staff_roles = ("coordinator", "admin")
role_labels = {"donor": "Donor", "ngo": "NGO", "coordinator": "Coordinator", "admin": "Admin"}

donor_types = ("Individual", "Restaurant", "Supermarket", "Bakery", "Hotel / Catering", "Other")
food_categories = ("Cooked Meals", "Bakery", "Fruits & Vegetables", "Dairy",
                   "Packaged Food", "Beverages", "Meat & Poultry", "Other")
units = ("kg", "portions", "liters", "boxes", "items")
cancel_reasons = ("Food is no longer available", "Donated elsewhere", "Quantity changed",
                  "Pickup is not possible", "Other")
statuses = ("Pending", "Allocated", "Delivered", "Cancelled", "Expired")

cities = ("Cairo", "Giza", "Fayoum", "Alexandria")

max_quantity = 10000

donation_fields = ["donation_id", "donor_id", "food_name", "category", "quantity", "unit",
                   "expiry_date", "pickup_location", "pickup_from", "pickup_until", "notes",
                   "status", "cancel_reason", "created_at", "updated_at", "city", "ngo_id", "created_at", "updated_at", "city", "ngo_id",
                   "allocated_at", "delivered_at"]

default_admin = {"full_name": "System Admin", "email": "admin@foodrescue.org",
                 "phone": "01000000000", "password": "Admin@12345"}
