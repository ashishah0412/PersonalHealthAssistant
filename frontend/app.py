# frontend/app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from PIL import Image, UnidentifiedImageError
from datetime import datetime, date
import os
import io
import requests

# ---------------------------
# Configuration
# ---------------------------
BACKEND_BASE = st.secrets.get("BACKEND_BASE", "http://127.0.0.1:8000")  # default backend URL
ASSETS_DIR = "assets"
UPLOAD_DIR = "uploads"  # local fallback (same as backend uploads dir)

# helper to call backend with error handling
def backend_get(path, params=None):
    try:
        resp = requests.get(BACKEND_BASE + path, params=params, timeout=4)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Backend GET {path} failed: {e}")
        return None

def backend_post(path, json=None, files=None, data=None):
    try:
        resp = requests.post(BACKEND_BASE + path, json=json, files=files, data=data, timeout=8)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Backend POST {path} failed: {e}")
        return None

# ---------------------------
# Helper utilities (same as your earlier functions)
# ---------------------------
# def load_image(name, fallback_text=None):
#     path = os.path.join(ASSETS_DIR, name)
#     if os.path.exists(path):
#         try:
#             return Image.open(path)
#         except UnidentifiedImageError:
#             return None
#     return None

def load_image(name, fallback_text=None):
    if not name:  # empty string or None
        return None
    path = os.path.join(ASSETS_DIR, name)
    if os.path.isfile(path):  # make sure it's a file
        try:
            return Image.open(path)
        except UnidentifiedImageError:
            return None
    return None


def parse_date(d):
    if not d:
        return None
    if isinstance(d, (date, datetime)):
        return d.date() if isinstance(d, datetime) else d
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(d, fmt).date()
        except Exception:
            pass
    return None

def calculate_age(dob):
    d = parse_date(dob)
    if not d:
        return None
    today = date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))

def calculate_bmi(weight_kg, height_cm):
    try:
        h = float(height_cm) / 100.0
        w = float(weight_kg)
        if h <= 0: return None
        return round(w / (h * h), 1)
    except Exception:
        return None

def nice_date(d):
    d2 = parse_date(d)
    return d2.strftime("%Y-%m-%d") if d2 else ""

# ---------------------------
# Initialize session state with fallback sample data
# ---------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# minimal fallback data is kept so frontend works if backend down
if "family" not in st.session_state:
    st.session_state.family = [
        {"id":1,"name":"Sophia Bennett","dob":"1995-06-15","gender":"Female","blood_type":"O+","height_cm":165,"weight_kg":62,"allergies":"None","chronic_conditions":[]},
        {"id":2,"name":"Liam Shah","dob":"2010-02-20","gender":"Male","blood_type":"A+","height_cm":140,"weight_kg":36,"allergies":"Peanuts","chronic_conditions":["Asthma"]}
    ]

if "medications" not in st.session_state:
    st.session_state.medications = [
        {"id":1,"member_id":1,"name":"Vitamin D","dosage":"100mg","freq":"once daily","start":"2024-01-01","end":"","doctor":"Dr. Emily Carter","status":"Active"}
    ]

if "reports" not in st.session_state:
    st.session_state.reports = [
        {"id":1,"member_id":1,"date":"2024-04-10","type":"Blood Test","lab":"HealthLab Diagnostics","doctor":"Dr. Emily Carter","file_path":None,"parsed":{"Glucose":95,"Cholesterol":180},"notes":"Demo"}
    ]

# ---------------------------
# Page layout & navigation (keeping your radio-based approach)
# ---------------------------
st.set_page_config(page_title="Health Assistant UI", layout="wide", initial_sidebar_state="expanded")
logo = load_image("logo.png")
col1, col2 = st.columns([1,8])
with col1:
    if logo:
        st.image(logo, width=80)
    else:
        st.markdown("**HealthAI**")
with col2:
    st.markdown("## AI-powered Personal Health Assistant (Frontend)")
    st.write("Frontend calls backend APIs (mock) — falls back to demo data if backend unavailable.")

st.sidebar.title("Navigation")
pages = [
    "Login / Auth (UI-only)",
    "Dashboard",
    "Reports",
    "Upload Report",
    "Medications",
    "Family",
    "Add Family Member",
    "Appointments (placeholder)",
    "Resources (placeholder)",
]
page = st.sidebar.radio("Go to", pages)

# helper: fetch family list from backend (or fallback)
def get_family():
    res = backend_get("/family")
    if res is None:
        return st.session_state.family
    return res

def get_reports(member_id=None):
    params = {"member_id": member_id} if member_id else {}
    res = backend_get("/reports", params=params)
    if res is None:
        # fallback filter on session_state
        if member_id:
            return [r for r in st.session_state.reports if r["member_id"] == member_id]
        return st.session_state.reports
    return res

def add_family_backend(payload):
    return backend_post("/family", json=payload)

def upload_report_backend(member_id, report_date, report_type, lab, doctor, uploaded_file):
    # prepare multipart/form-data
    data = {
        "member_id": str(member_id),
        "report_date": report_date,
        "report_type": report_type,
        "lab_name": lab or "",
        "doctor": doctor or ""
    }
    files = None
    if uploaded_file:
        files = {"file": (uploaded_file.name, uploaded_file.getbuffer(), uploaded_file.type)}
    return backend_post("/reports/upload", data=data, files=files)

def parse_report_backend(report_id):
    return backend_post(f"/reports/{report_id}/parse")

def list_medications_backend(member_id=None):
    params = {"member_id": member_id} if member_id else None
    try:
        resp = requests.get(f"{BACKEND_BASE}/medications", params=params, timeout=4)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        if member_id:
            return [m for m in st.session_state.medications if m["member_id"] == member_id]
        return st.session_state.medications

def add_medication_backend(payload):
    return backend_post("/medications", json=payload)

# ---------------------------
# small helper: select member UI
# ---------------------------
def member_selector(label="Select Member", key="selected_member", use_backend=True):
    members = get_family() if use_backend else st.session_state.family
    options = {m["name"]: m["id"] for m in members}
    if not options:
        return None
    default_name = list(options.keys())[0]
    sel_name = st.selectbox(label, list(options.keys()), index=0, key=key)
    selected_id = options.get(sel_name)
    selected = next((m for m in members if m["id"] == selected_id), None)
    return selected

# ---------------------------
# PAGE: Login / Auth (UI-only)
# ---------------------------
def page_login():
    st.title("Welcome to HealthHub (Login)")
    st.write("Demo login — calls backend /auth/login (mock).")
    with st.form("login_form"):
        email = st.text_input("Email", value="demo_user@example.com")
        pwd = st.text_input("Password", type="password", value="demo")
        submitted = st.form_submit_button("Login")
        if submitted:
            res = backend_post("/auth/login", json={"email": email, "password": pwd})
            if res:
                st.success(f"Mock login OK — token: {res.get('token')[:12]}...")
                st.session_state.logged_in = True
            else:
                st.error("Login failed — backend not reachable or bad creds (mock).")

# ---------------------------
# PAGE: Dashboard
# ---------------------------
def page_dashboard():
    st.title("Family Health Dashboard")
    st.write("Manage and monitor the health of your loved ones.")
    selected = member_selector()
    if not selected:
        st.warning("No family members found. Use 'Add Family Member' screen.")
        return

    age = calculate_age(selected.get("dob"))
    bmi = calculate_bmi(selected.get("weight_kg"), selected.get("height_cm"))
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"{selected['name']}")
        st.write(f"Age: {age} • Blood Type: {selected.get('blood_type','-')} • Allergies: {selected.get('allergies','-')}")
    with col2:
        img = load_image(selected.get("photo") or "")
        if img:
            st.image(img, width=80)
        else:
            st.caption("No profile image")

    st.markdown("### Key Health Metrics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Heart Rate", "72 bpm", "-1")
    c2.metric("Blood Pressure", "120/80", "-1%")
    c3.metric("Sleep Duration", "7.5 hrs", "+0.2")
    c4.metric("BMI", f"{bmi if bmi else '—'}", "")

    st.markdown("### Health Trends")
    dates = pd.date_range(end=pd.Timestamp.today(), periods=12).to_pydatetime().tolist()
    hr_values = np.round(70 + 6*np.sin(np.linspace(0, 3.5, 12)) + np.random.normal(0,1,12)).tolist()
    sleep_values = np.round(7 + 0.6*np.cos(np.linspace(0, 3.5, 12)) + np.random.normal(0,0.2,12),1).tolist()

    df_hr = pd.DataFrame({"date": dates, "value": hr_values})
    df_sleep = pd.DataFrame({"date": dates, "value": sleep_values})

    cola, colb = st.columns(2)
    with cola:
        fig_hr = px.line(df_hr, x="date", y="value", title="Heart Rate Trend (Last 3 Months)")
        fig_hr.update_layout(margin=dict(l=0,r=0,t=30,b=0), height=300, yaxis_title="bpm")
        st.plotly_chart(fig_hr, use_container_width=True)
    with colb:
        fig_sleep = px.line(df_sleep, x="date", y="value", title="Sleep Duration Trend")
        fig_sleep.update_layout(margin=dict(l=0,r=0,t=30,b=0), height=300, yaxis_title="hrs")
        st.plotly_chart(fig_sleep, use_container_width=True)

    st.markdown("### Current Medications")
    meds = list_medications_backend(selected["id"])
    if meds:
        df_m = pd.DataFrame(meds)[["name","dosage","freq","start","end","doctor","status"]]
        st.table(df_m.rename(columns={"name":"Medication","dosage":"Dosage","freq":"Frequency","start":"Start Date","end":"End Date","doctor":"Doctor","status":"Status"}))
    else:
        st.info("No active medications recorded.")

    st.markdown("### Latest Report Summary")
    member_reports = sorted(get_reports(selected["id"]), key=lambda r: r["date"], reverse=True)
    if member_reports:
        latest = member_reports[0]
        st.write(f"**{latest['type']}** • {nice_date(latest['date'])} • {latest.get('lab','')}")
        st.write(latest.get("notes","No AI summary available (demo)."))
    else:
        st.info("No diagnostic reports uploaded for this member.")

# ---------------------------
# PAGE: Reports & Trends
# ---------------------------
def page_reports():
    st.title("Diagnostic Reports — Trend Analysis")
    selected = member_selector()
    if not selected:
        st.warning("Please add a family member.")
        return

    tabs = st.tabs(["All Reports", "Trend Analysis", "AI Insights"])

    with tabs[0]:
        st.subheader("All Reports")
        member_reports = sorted(get_reports(selected["id"]), key=lambda r: r["date"], reverse=True)
        if not member_reports:
            st.info("No reports found.")
        else:
            for r in member_reports:
                st.markdown(f"**{r['type']}** — {nice_date(r['date'])} • {r.get('lab','')}")
                parsed = r.get("parsed", {})
                if parsed:
                    st.table(pd.DataFrame(list(parsed.items()), columns=["Parameter","Value"]))
                st.write(r.get("notes",""))
                if r.get("file_path"):
                    st.write(f"File stored at backend: {r.get('file_path')}")

    with tabs[1]:
        st.subheader("Trends for Common Parameters")
        member_reports = sorted(get_reports(selected["id"]), key=lambda r: r["date"])
        if len(member_reports) < 1:
            st.info("Need at least one report to show trend.")
        else:
            param = st.selectbox("Select parameter", options=["Glucose","Cholesterol","TSH"], key="trend_param")
            dates = []
            vals = []
            for r in member_reports:
                if r.get("parsed") and param in r["parsed"]:
                    dates.append(parse_date(r["date"]) or datetime.today().date())
                    vals.append(r["parsed"][param])
            if vals:
                df = pd.DataFrame({"date": dates, "value": vals})
                fig = px.line(df, x="date", y="value", markers=True, title=f"{param} over time")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No recorded values for {param}.")

    with tabs[2]:
        st.subheader("AI-generated summaries (demo)")
        # Simple cholesterol trend check
        vals = []
        for r in sorted(get_reports(selected["id"]), key=lambda r: r["date"]):
            if r.get("parsed") and "Cholesterol" in r["parsed"]:
                vals.append(r["parsed"]["Cholesterol"])
        if len(vals) >= 2:
            delta = vals[-1] - vals[0]
            pct = round((delta / vals[0]) * 100, 1)
            if pct > 3:
                st.warning(f"Your last {len(vals)} cholesterol tests show an increasing trend (+{pct}%). Consider lifestyle changes.")
            else:
                st.success("Cholesterol trend is stable.")
        else:
            st.info("Not enough data for cholesterol trend.")
        st.markdown("**Example AI notes (demo)**")
        st.write("- Glucose levels within normal range in latest report.")
        st.write("- Consider vitamin D test in winter months.")

# ---------------------------
# PAGE: Upload Diagnostic Report (UI-only) - calls backend
# ---------------------------
def page_upload_report():
    st.title("Upload Diagnostic Report")
    selected = member_selector("Select Family Member to attach report to", key="upload_member")
    with st.form("upload_form", clear_on_submit=False):
        report_name = st.text_input("Report Name", placeholder="e.g., Blood Test Results")
        report_date = st.date_input("Date of Report", value=datetime.today())
        report_type = st.selectbox("Report Type", ["Blood Test","CT Scan","ECG","MRI","Liver Function","Other"])
        lab_name = st.text_input("Lab Name (optional)")
        doctor_name = st.text_input("Consulting Doctor (optional)")
        uploaded_file = st.file_uploader("Upload a file (PDF, JPG, PNG)", type=["pdf","png","jpg","jpeg"])
        use_ai = st.checkbox("Use AI to automatically extract parameters (demo)", value=True)
        submitted = st.form_submit_button("Upload Report")
        if submitted:
            if not selected:
                st.error("Please select a family member.")
            else:
                # call backend
                backend_resp = upload_report_backend(selected["id"], report_date.strftime("%Y-%m-%d"), report_type, lab_name, doctor_name, uploaded_file)
                if backend_resp:
                    st.success("Report uploaded to backend (mock). You can trigger parse using report ID.")
                else:
                    # fallback: save to session_state
                    new_id = max([r["id"] for r in st.session_state.reports] + [0]) + 1
                    parsed = {"Glucose": 95, "Cholesterol": 180} if use_ai else {}
                    fname = None
                    if uploaded_file:
                        fname = uploaded_file.name
                    st.session_state.reports.append({
                        "id": new_id,
                        "member_id": selected["id"],
                        "date": report_date.strftime("%Y-%m-%d"),
                        "type": report_type,
                        "lab": lab_name,
                        "doctor": doctor_name,
                        "file_path": fname,
                        "parsed": parsed,
                        "notes": "Demo fallback upload"
                    })
                    st.success("Report saved in local session (fallback).")

# ---------------------------
# PAGE: Medications (calls backend)
# ---------------------------
def page_medications():
    st.title("Medications")
    selected = member_selector()
    if not selected:
        st.warning("Please add a family member first.")
        return

    st.subheader("Current Medications")
    meds = list_medications_backend(selected["id"])
    if meds:
        df = pd.DataFrame(meds)[["name","dosage","freq","start","end","doctor","status"]]
        st.table(df.rename(columns={"name":"Medication","dosage":"Dosage","freq":"Frequency","start":"Start Date","end":"End Date","doctor":"Doctor","status":"Status"}))
    else:
        st.info("No current medications for this member.")

    st.markdown("### Add / Update Medication (UI -> backend)")
    with st.form("add_med"):
        med_name = st.text_input("Medicine Name")
        dosage = st.text_input("Dosage (e.g., 500mg)")
        freq = st.selectbox("Frequency", ["Once daily", "Twice daily", "Three times daily", "Before bed", "As needed"])
        start = st.date_input("Start Date", value=datetime.today())
        end = st.date_input("End Date", value=datetime.today())
        doctor = st.text_input("Consulting Doctor")
        status = st.selectbox("Status", ["Active","Stopped"])
        if st.form_submit_button("Save medication"):
            payload = {
                "member_id": selected["id"],
                "name": med_name,
                "dosage": dosage,
                "freq": freq,
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
                "doctor": doctor,
                "status": status
            }
            resp = add_medication_backend(payload)
            if resp:
                st.success("Medication added via backend (mock).")
            else:
                # fallback
                new_id = max([m["id"] for m in st.session_state.medications] + [0]) + 1
                payload["id"] = new_id
                st.session_state.medications.append(payload)
                st.success("Medication saved in local session (fallback).")

# ---------------------------
# PAGE: Family + Add Member (calls backend)
# ---------------------------
def page_family():
    st.title("Family")
    members = get_family()
    if not members:
        st.info("No family members found.")
        return
    for m in members:
        c1, c2 = st.columns([1,8])
        with c1:
            img = load_image(m.get("photo") or "")
            if img:
                st.image(img, width=80)
            else:
                st.markdown("👤")
        with c2:
            st.markdown(f"**{m['name']}**")
            st.write(f"Age: {calculate_age(m['dob'])} • Blood: {m.get('blood_type','-')} • Allergies: {m.get('allergies','-')}")

def page_add_family_member():
    st.title("Add a Family Member")
    with st.form("add_member", clear_on_submit=True):
        full_name = st.text_input("Full Name")
        relation = st.selectbox("Relationship", ["Self","Spouse","Child","Parent","Other"])
        dob = st.date_input("Date of Birth")
        gender = st.selectbox("Gender", ["Female","Male","Other","Prefer not to say"])
        blood = st.text_input("Blood Type", placeholder="e.g., O+")
        height = st.number_input("Height (cm)", min_value=40, max_value=250, value=165)
        weight = st.number_input("Weight (kg)", min_value=5, max_value=300, value=70)
        allergies = st.text_input("Allergies (comma separated)")
        chronic = st.text_input("Chronic Conditions (comma separated)")
        photo = st.file_uploader("Upload profile photo (optional)", type=["png","jpg","jpeg"])
        if st.form_submit_button("Add Family Member"):
            payload = {
                "name": full_name,
                "dob": dob.strftime("%Y-%m-%d"),
                "gender": gender,
                "blood_type": blood,
                "height_cm": height,
                "weight_kg": weight,
                "allergies": allergies,
                "chronic_conditions": [c.strip() for c in chronic.split(",")] if chronic else []
            }
            res = add_family_backend(payload)
            if res:
                st.success(f"{full_name} added via backend (mock).")
            else:
                # fallback local
                new_id = max([m["id"] for m in st.session_state.family] + [0]) + 1
                payload["id"] = new_id
                st.session_state.family.append(payload)
                st.success(f"{full_name} added to local session (fallback).")

# ---------------------------
# Simple placeholders
# ---------------------------
def page_appointments():
    st.title("Appointments (placeholder)")
    st.info("Not implemented in prototype.")

def page_resources():
    st.title("Resources")
    st.write("Guides and resources (placeholder)")

# ---------------------------
# Router
# ---------------------------
if page == "Login / Auth (UI-only)":
    page_login()
elif page == "Dashboard":
    page_dashboard()
elif page == "Reports":
    page_reports()
elif page == "Upload Report":
    page_upload_report()
elif page == "Medications":
    page_medications()
elif page == "Family":
    page_family()
elif page == "Add Family Member":
    page_add_family_member()
elif page == "Appointments (placeholder)":
    page_appointments()
elif page == "Resources (placeholder)":
    page_resources()
else:
    st.write("Page not found")

st.markdown("---")
st.caption("Frontend uses backend APIs at " + BACKEND_BASE + " (mock).")
