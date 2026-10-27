"""
FairShift End-to-End Operational Verification Script
Tests all core workflows:
1. Worker Portal (Construction & College)
2. Attendance Check-in and Check-out
3. Transparent Salary Calculations
4. Retaliation-Free Safety Reporting (Anonymous & Ref Code)
5. Admin Dashboard & Hazard Status Updates (Open -> Under Review -> Resolved)
6. Public Reference Tracker
"""

import app
import database

client = app.app.test_client()

print("=== 1. Testing Worker Portal ===")
r_w_con = client.get("/worker?industry=Construction")
assert r_w_con.status_code == 200, f"Worker Construction failed: {r_w_con.status_code}"
assert b"Marcus Vance" in r_w_con.data, "Worker Construction missing Marcus Vance"

r_w_col = client.get("/worker?industry=College")
assert r_w_col.status_code == 200, f"Worker College failed: {r_w_col.status_code}"
assert b"Sarah Jenkins" in r_w_col.data, "Worker College missing Sarah Jenkins"
print("Worker portal test: PASSED (Construction & College sectors verified)")

print("=== 2. Testing Attendance Check-In and Check-Out ===")
conn = database.get_db()
w = conn.execute("SELECT * FROM workers WHERE worker_code = 'CON-101'").fetchone()
conn.close()

# Clock in
r_in = client.post("/worker/check-in", data={
    "worker_id": w["id"],
    "worker_code": w["worker_code"],
    "industry": w["industry"],
    "notes": "Starting Morning Shift on Tower 1"
}, follow_redirects=True)
assert r_in.status_code == 200, f"Check-in failed: {r_in.status_code}"

conn = database.get_db()
active = conn.execute("SELECT * FROM attendance WHERE worker_id = ? AND check_out IS NULL", (w["id"],)).fetchone()
conn.close()
assert active is not None, "Active shift was not recorded in DB"
print("Check-in test: PASSED (Active shift recorded with timestamp)")

# Clock out with simulated 9.5 hours
r_out = client.post("/worker/check-out", data={
    "attendance_id": active["id"],
    "worker_code": w["worker_code"],
    "industry": w["industry"],
    "notes": "Completed tower scaffolding check",
    "simulated_hours": "9.5"
}, follow_redirects=True)
assert r_out.status_code == 200, f"Check-out failed: {r_out.status_code}"

conn = database.get_db()
closed = conn.execute("SELECT * FROM attendance WHERE id = ?", (active["id"],)).fetchone()
conn.close()
assert closed["check_out"] is not None, "Check out timestamp missing"
assert closed["total_hours"] == 9.5, f"Expected 9.5h, got {closed['total_hours']}"
assert closed["overtime_hours"] == 1.5, f"Expected 1.5h OT, got {closed['overtime_hours']}"
print("Check-out test: PASSED (Shift closed, total_hours=9.5, overtime_hours=1.5 calculated)")

print("=== 3. Testing Salary Calculator ===")
calc = app.calculate_salary(base_hours=40, hourly_rate=25, overtime_hours=8, multiplier=1.5)
assert calc["regular_pay"] == 1000.0, f"Regular pay calculation error: {calc['regular_pay']}"
assert calc["overtime_pay"] == 300.0, f"Overtime pay calculation error: {calc['overtime_pay']}"
assert calc["gross_pay"] == 1300.0, f"Gross pay calculation error: {calc['gross_pay']}"
assert "FairShift Notice" in calc["disclaimer"], "Missing transparency disclaimer"
print("Salary calculator test: PASSED (Base: $1000, Overtime: $300, Gross: $1300, Disclaimer verified)")

print("=== 4. Testing Safety Hazard Reporting ===")
r_rep = client.post("/worker/report-hazard", data={
    "worker_id": w["id"],
    "worker_code": w["worker_code"],
    "industry": "Construction",
    "category": "Unsafe Scaffolding",
    "severity": "Critical",
    "location": "Level 6 Perimeter Planks",
    "description": "Planks lack tie-down cleat; high wind displacement hazard",
    "is_anonymous": "on"
}, follow_redirects=True)
assert r_rep.status_code == 200, f"Hazard reporting failed: {r_rep.status_code}"

conn = database.get_db()
new_rep = conn.execute("SELECT * FROM safety_reports WHERE location = 'Level 6 Perimeter Planks'").fetchone()
conn.close()
assert new_rep is not None, "Hazard report not found in DB"
assert new_rep["is_anonymous"] == 1, "Anonymous flag not set"
assert new_rep["worker_id"] is None, "Worker ID should be null for anonymous protection"
assert new_rep["status"] == "Open", "Default status must be Open"
ref_no = new_rep["reference_no"]
print(f"Safety reporting test: PASSED (Reference: {ref_no}, Anonymous Protection Active)")

print("=== 5. Testing Admin Dashboard & Report Status Updates ===")
r_admin = client.get("/admin")
assert r_admin.status_code == 200, f"Admin dashboard failed: {r_admin.status_code}"
assert b"Workforce Safety & Compliance Dashboard" in r_admin.data, "Admin dashboard missing header"
assert b"Fatigue & Overtime Warning Center" in r_admin.data, "Admin dashboard missing fatigue center"

# Update report status to 'Under Review'
r_up1 = client.post(f"/admin/safety-reports/{new_rep['id']}/update", data={
    "status": "Under Review",
    "admin_notes": "Safety inspector dispatched to secure perimeter planks.",
    "industry_filter": "All"
}, follow_redirects=True)
assert r_up1.status_code == 200, "Status update to Under Review failed"

# Update report status to 'Resolved'
r_up2 = client.post(f"/admin/safety-reports/{new_rep['id']}/update", data={
    "status": "Resolved",
    "admin_notes": "All planks anchored with heavy duty clamps. Verified safe.",
    "industry_filter": "All"
}, follow_redirects=True)
assert r_up2.status_code == 200, "Status update to Resolved failed"

conn = database.get_db()
resolved_rep = conn.execute("SELECT * FROM safety_reports WHERE id = ?", (new_rep["id"],)).fetchone()
conn.close()
assert resolved_rep["status"] == "Resolved", f"Status not updated to Resolved: {resolved_rep['status']}"
assert "anchored with heavy duty clamps" in resolved_rep["admin_notes"], "Admin notes not saved"
print("Admin dashboard and status update test: PASSED (Report transitioned Open -> Under Review -> Resolved)")

print("=== 6. Testing Public Reference Tracker ===")
r_track = client.get(f"/track/{ref_no}")
assert r_track.status_code == 200, f"Track report failed: {r_track.status_code}"
assert ref_no.encode() in r_track.data, f"Reference code {ref_no} not shown on tracker"
assert b"Resolved" in r_track.data, "Resolved status not shown on tracker"
print("Hazard tracker lookup test: PASSED")

print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY WITH 0 ERRORS!")
