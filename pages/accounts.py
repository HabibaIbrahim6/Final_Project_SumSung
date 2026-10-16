import streamlit as st

import config
from session import (
    flash,
    get_allocation_service,
    get_user_service,
    login,
    require_access,
    show_flashes,
)
from ui import hero
from validators import FoodRescueError

role_choices = {"Donor (restaurant, shop, individual)": "donor", "NGO representative": "ngo"}


def login_register_page():
    show_flashes()
    hero(
        "Welcome to our Food Rescue Coordinator app!",
        "Connect surplus food with the NGOs that need it before it expires.",
    )
    login_tab, register_tab = st.tabs(["Login", "Register"])
    with login_tab:
        show_login_form()
    with register_tab:
        show_register_form()


def show_login_form():
    users = get_user_service()
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")
    if submitted:
        try:
            user = users.authenticate(email, password)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            login(user)
            st.rerun()


def show_register_form():
    users = get_user_service()
    st.write("Coordinator and admin accounts are created by an administrator.")
    role_label = st.radio("I am registering as", list(role_choices), horizontal=True)
    role = role_choices[role_label]
    count = st.session_state.get("form_count", 0)

    if role == "ngo":
        st.info("For security, an administrator must link this account to its registered NGO.")

    with st.form("register_form_" + str(count)):
        col1, col2 = st.columns(2)
        full_name = col1.text_input("Full name")
        email = col2.text_input("Email")
        phone = col1.text_input("Phone", placeholder="01001234567")
        donor_type = None
        organization = ""
        if role == "donor":
            donor_type = col2.selectbox("Donor type", config.donor_types)
            organization = st.text_input("Organization name (optional)")
        password = col1.text_input("Password", type="password",
                                   help="At least 8 characters with upper-case, lower-case and a digit.")
        confirm = col2.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account", type="primary")

    if submitted:
        if password != confirm:
            st.error("Passwords do not match.")
            return
        try:
            user = users.register(full_name, email, password, phone, role=role,
                                  donor_type=donor_type, organization=organization)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", f"Account {user.user_id} created. You can log in now.")
            st.session_state["form_count"] = count + 1
            st.rerun()


def admin_users_page():
    admin = require_access("manage_users")
    users = get_user_service()
    show_flashes()

    hero("User Management", "Manage accounts, roles and access.")
    counts = users.count_by_role()
    columns = st.columns(len(config.roles) + 1)
    columns[0].metric("Total users", sum(counts.values()))
    for column, role in zip(columns[1:], config.roles):
        column.metric(config.role_labels[role], counts[role])

    list_tab, manage_tab, create_tab = st.tabs(["All users", "Manage a user", "Create staff account"])
    with list_tab:
        show_user_list(users)
    with manage_tab:
        show_manage_user(admin, users)
    with create_tab:
        show_create_staff(admin, users)


def show_user_list(users):
    col1, col2, col3 = st.columns([2, 2, 3])
    roles = col1.multiselect("Role", config.roles, format_func=config.role_labels.get)
    state = col2.radio("Status", ["All", "Active", "Inactive"], horizontal=True)
    query = col3.text_input("Search", placeholder="ID, name or email")
    is_active = {"All": None, "Active": True, "Inactive": False}[state]

    found = users.list_users(roles, is_active, query)
    if not found:
        st.warning("No users match the current filters.")
        return
    rows = []
    for user in found:
        rows.append({"ID": user.user_id, "Name": user.full_name, "Email": user.email,
                     "Phone": user.phone, "Role": user.label,
                     "Active": "Yes" if user.is_active else "No", "Created": user.created_at})
    st.dataframe(rows, hide_index=True)


def show_manage_user(admin, users):
    options = {}
    for user in users.list_users():
        options[f"{user.user_id} - {user.full_name} ({user.label})"] = user
    target = options[st.selectbox("Select a user", list(options))]
    is_self = target.user_id == admin.user_id

    status = "active" if target.is_active else "deactivated"
    st.write(f"**{target.full_name}** - {target.email} - {status}")
    if is_self:
        st.info("This is your own account. You cannot change your role or deactivate yourself.")

    col1, col2 = st.columns(2)
    new_role = col1.selectbox("Role", config.roles, format_func=config.role_labels.get,
                              index=config.roles.index(target.role), disabled=is_self,
                              key="role_" + target.user_id)
    ngo_id = None
    if new_role == "ngo":
        allocation = get_allocation_service()
        ngo_options = {
            f"{ngo['name']} — {ngo['location']}": ngo["id"]
            for ngo in allocation.ngos
        }
        if ngo_options:
            labels = list(ngo_options)
            existing = next(
                (label for label, value in ngo_options.items()
                 if str(value) == str(getattr(target, "ngo_id", ""))),
                labels[0],
            )
            ngo_id = ngo_options[
                st.selectbox(
                    "Link representative to NGO",
                    labels,
                    index=labels.index(existing),
                    key="ngo_link_" + target.user_id,
                )
            ]
        else:
            st.warning("Create an NGO profile before assigning the NGO role.")
    if col1.button("Update role", disabled=is_self, key="role_button_" + target.user_id):
        try:
            users.set_role(admin, target.user_id, new_role, ngo_id=ngo_id)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", f"{target.full_name} is now {config.role_labels[new_role]}.")
            st.rerun()

    col2.write("Account status")
    button_text = "Deactivate account" if target.is_active else "Activate account"
    if col2.button(button_text, disabled=is_self, key="active_button_" + target.user_id):
        try:
            users.set_active(admin, target.user_id, not target.is_active)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", "Account status updated.")
            st.rerun()

    with st.expander("Reset password"):
        with st.form("reset_form_" + target.user_id):
            new_password = st.text_input("New temporary password", type="password")
            reset_clicked = st.form_submit_button("Reset password")
        if reset_clicked:
            try:
                users.reset_password(admin, target.user_id, new_password)
            except FoodRescueError as error:
                st.error(str(error))
            else:
                flash("success", "Password reset.")
                st.rerun()


def show_create_staff(admin, users):
    with st.form("create_staff_form"):
        col1, col2 = st.columns(2)
        full_name = col1.text_input("Full name")
        email = col2.text_input("Email")
        phone = col1.text_input("Phone", placeholder="01001234567")
        role = col2.selectbox("Role", config.staff_roles, format_func=config.role_labels.get)
        password = st.text_input("Temporary password", type="password")
        submitted = st.form_submit_button("Create account", type="primary")
    if submitted:
        try:
            users.register(full_name, email, password, phone, role=role, actor=admin)
        except FoodRescueError as error:
            st.error(str(error))
        else:
            flash("success", f"{config.role_labels[role]} account created.")
            st.rerun()
