import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import date, timedelta

# ---------------- CONFIG ----------------
st.set_page_config(page_title="TA Hours Tracker", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

COURSE_NAME = "APES3078A"  # predefined course
THREE_MONTH_CAP = 100    # example cap (adjust as needed)

RESPONSIBILITIES = [
    "Lab",
    "Marking",
    "Quiz",
    "Invigilation",
    "Other"
]

# ---------------- HELPERS ----------------
def week_start(d):
    return d - timedelta(days=d.weekday())

def get_profile(user_id):
    return (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

# ---------------- AUTH ----------------
def login():
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state.user = res.user
            st.rerun()
        except Exception as e:
            st.error("Invalid login details")

# ---------------- TA: LOG HOURS ----------------
def log_hours(user):
    st.subheader("Log Hours")

    with st.form("log_form"):
        entry_date = st.date_input("Date", value=date.today())
        responsibility = st.selectbox("Responsibility", RESPONSIBILITIES)
        hours = st.number_input("Hours", min_value=0.25, step=0.25)
        notes = st.text_area("Notes (optional)")

        submitted = st.form_submit_button("Submit")

        if submitted:
            if entry_date > date.today():
                st.error("Future dates not allowed")
                return

            supabase.table("ta_hours").insert({
                "user_id": user.id,
                "entry_date": entry_date.isoformat(),
                "week_start": week_start(entry_date).isoformat(),
                "responsibility": responsibility,
                "hours": hours,
                "notes": notes
            }).execute()

            st.success("Hours logged successfully")
            st.rerun()

# ---------------- TA: VIEW / EDIT HOURS ----------------
def my_hours(user):
    st.subheader("My Hours")

    res = (
        supabase.table("ta_hours")
        .select("*")
        .eq("user_id", user.id)
        .order("entry_date", desc=True)
        .execute()
    )

    if not res.data:
        st.info("No entries yet")
        return

    df = pd.DataFrame(res.data)
    st.dataframe(df, use_container_width=True)

    # Rolling 3-month warning
    three_months_ago = date.today() - timedelta(days=90)
    total_90 = df[pd.to_datetime(df["entry_date"]).dt.date >= three_months_ago]["hours"].sum()

    if total_90 >= THREE_MONTH_CAP:
        st.warning(f"⚠️ 3-month total: {total_90} hours (cap: {THREE_MONTH_CAP})")

    # Edit / delete
    st.markdown("### Edit or delete an entry")
    entry_id = st.selectbox("Select entry ID", df["id"])

    entry = df[df["id"] == entry_id].iloc[0]

    new_hours = st.number_input("Update hours", value=float(entry["hours"]))
    new_notes = st.text_area("Update notes", value=entry["notes"] or "")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Update"):
            supabase.table("ta_hours").update({
                "hours": new_hours,
                "notes": new_notes
            }).eq("id", entry_id).execute()
            st.success("Entry updated")
            st.rerun()

    with col2:
        if st.button("Delete"):
            supabase.table("ta_hours").delete().eq("id", entry_id).execute()
            st.warning("Entry deleted")
            st.rerun()

# ---------------- ADMIN DASHBOARD ----------------
def admin_dashboard():
    st.subheader("Admin Dashboard")

    res = supabase.table("ta_hours").select("*").execute()
    if not res.data:
        st.info("No data yet")
        return

    df = pd.DataFrame(res.data)
    df["entry_date"] = pd.to_datetime(df["entry_date"])

    st.dataframe(df, use_container_width=True)

    st.markdown("### Weekly totals")
    weekly = df.groupby(["user_id", "week_start"])["hours"].sum().reset_index()
    st.dataframe(weekly, use_container_width=True)

    st.markdown("### 3-Month totals")
    cutoff = date.today() - timedelta(days=90)
    totals = (
        df[df["entry_date"].dt.date >= cutoff]
        .groupby("user_id")["hours"]
        .sum()
        .reset_index()
    )
    st.dataframe(totals, use_container_width=True)

# ---------------- MAIN ----------------
if "user" not in st.session_state:
    login()
else:
    user = st.session_state.user
    profile = get_profile(user.id)

    st.sidebar.success(f"Logged in as {profile['name']}")
    if st.sidebar.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

    if profile["role"] == "admin":
        admin_dashboard()
    else:
        log_hours(user)
        st.divider()
        my_hours(user)
