"""
FairShift Final Live Functionality Audit Script
Executes full HTTP requests against the live running server at http://127.0.0.1:8080
"""

import sys
import urllib.request
import urllib.parse
from http.cookiejar import CookieJar

BASE_URL = "http://127.0.0.1:8080"
cookie_jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

results = []

def record(test_name, success, details=""):
    results.append({"name": test_name, "success": success, "details": details})
    status_str = "PASS" if success else "FAIL"
    print(f"[{status_str}] {test_name}: {details}")

print("=== Starting FairShift Live Functionality Audit ===")

# Audit 1: Launch and Root Redirect
try:
    req = urllib.request.Request(f"{BASE_URL}/", headers={"User-Agent": "FairShiftAuditor"})
    resp = opener.open(req)
    url_landed = resp.geturl()
    assert resp.getcode() == 200
    assert "/worker" in url_landed
    record("1. Server Launch & Root Redirect", True, f"HTTP 200, successfully redirected to {url_landed}")
except Exception as e:
    record("1. Server Launch & Root Redirect", False, str(e))

# Audit 2: Static Assets Availability
try:
    req = urllib.request.Request(f"{BASE_URL}/static/style.css")
    resp = opener.open(req)
    content = resp.read()
    assert resp.getcode() == 200
    assert len(content) > 1000
    assert b"--primary" in content
    record("2. Static Assets (style.css)", True, f"HTTP 200, CSS delivered ({len(content)} bytes)")
except Exception as e:
    record("2. Static Assets (style.css)", False, str(e))

# Audit 3: Industry Options - Construction Sector
try:
    req = urllib.request.Request(f"{BASE_URL}/worker?industry=Construction")
    resp = opener.open(req)
    body = resp.read().decode("utf-8")
    assert resp.getcode() == 200
    assert "Construction Trades" in body
    assert "CON-101" in body
    assert "Marcus Vance" in body
    assert "Transparent Salary Calculator" in body
    record("3. Worker Portal - Construction Sector", True, "HTTP 200, Construction profiles, roles, and UI rendered")
except Exception as e:
    record("3. Worker Portal - Construction Sector", False, str(e))

# Audit 4: Industry Options - College Sector
try:
    req = urllib.request.Request(f"{BASE_URL}/worker?industry=College")
    resp = opener.open(req)
    body = resp.read().decode("utf-8")
    assert resp.getcode() == 200
    assert "College & Educational Support Staff" in body
    assert "COL-201" in body
    assert "Sarah Jenkins" in body
    record("4. Worker Portal - College Sector", True, "HTTP 200, College profiles, roles, and UI rendered")
except Exception as e:
    record("4. Worker Portal - College Sector", False, str(e))

# Audit 5: Salary Calculation on Worker Portal
try:
    params = urllib.parse.urlencode({"industry": "Construction", "calc_base": "40.0", "calc_rate": "30.0", "calc_ot": "10.0"})
    req = urllib.request.Request(f"{BASE_URL}/worker?{params}")
    resp = opener.open(req)
    body = resp.read().decode("utf-8")
    assert resp.getcode() == 200
    # Base: 40 * 30 = $1,200.00; OT: 10 * 45 = $450.00; Gross: $1,650.00
    assert "$1,200.00" in body
    assert "$450.00" in body
    assert "$1,650.00" in body
    assert "FairShift Notice: This calculation represents estimated gross earnings" in body
    record("5. Transparent Salary Calculator (Sample Inputs)", True, "HTTP 200, Base $1,200.00 + OT $450.00 = Gross $1,650.00 verified with disclaimer")
except Exception as e:
    record("5. Transparent Salary Calculator (Sample Inputs)", False, str(e))

# Audit 6: Attendance Check-In Flow
try:
    data = urllib.parse.urlencode({
        "worker_id": 3,
        "worker_code": "CON-103",
        "industry": "Construction",
        "notes": "Auditing subpanel grounding"
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/worker/check-in", data=data)
    resp = opener.open(req)
    body = resp.read().decode("utf-8")
    assert resp.getcode() == 200
    assert "Shift Currently Active" in body
    record("6. Attendance Check-In", True, "HTTP 200, Shift active status banner confirmed in response")
except Exception as e:
    record("6. Attendance Check-In", False, str(e))

# Audit 7: Attendance Check-Out Flow
try:
    # Find active shift ID from worker portal page
    req = urllib.request.Request(f"{BASE_URL}/worker?industry=Construction&worker_code=CON-103")
    resp = opener.open(req)
    body = resp.read().decode("utf-8")
    
    # Extract attendance_id
    import re
    match = re.search(r'name="attendance_id"\s+value="(\d+)"', body)
    assert match is not None, "Active attendance_id not found in check-out form"
    att_id = match.group(1)

    data = urllib.parse.urlencode({
        "attendance_id": att_id,
        "worker_code": "CON-103",
        "industry": "Construction",
        "notes": "Audit completed safely",
        "simulated_hours": "9.5"
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/worker/check-out", data=data)
    resp = opener.open(req)
    body = resp.read().decode("utf-8")
    assert resp.getcode() == 200
    assert "Shift completed! Total: 9.50 hrs (Overtime: 1.50 hrs)" in body
    record("7. Attendance Check-Out", True, f"HTTP 200, Shift closed (attendance_id={att_id}, 9.50h total, 1.50h OT calculated)")
except Exception as e:
    record("7. Attendance Check-Out", False, str(e))

# Audit 8: Submit Safety Report & Verify in Admin Dashboard
test_ref_no = None
try:
    report_location = "Building C Roof Access Hatch"
    report_desc = "Hatch hinge is rusted sheared; access door blew open during wind gusts."
    data = urllib.parse.urlencode({
        "worker_id": 1,
        "worker_code": "CON-101",
        "industry": "Construction",
        "category": "Unsafe Scaffolding",
        "severity": "High",
        "location": report_location,
        "description": report_desc,
        "is_anonymous": "on"
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/worker/report-hazard", data=data)
    resp = opener.open(req)
    body = resp.read().decode("utf-8")
    assert resp.getcode() == 200
    
    # Extract generated reference number
    match = re.search(r'(HAZ-CON-\d{4})', body)
    assert match is not None, "Generated reference number not found in flash response"
    test_ref_no = match.group(1)
    
    # Verify in Admin Dashboard
    req_admin = urllib.request.Request(f"{BASE_URL}/admin?industry=Construction")
    resp_admin = opener.open(req_admin)
    body_admin = resp_admin.read().decode("utf-8")
    assert resp_admin.getcode() == 200
    assert test_ref_no in body_admin, f"Reference {test_ref_no} not found in admin dashboard"
    assert report_location in body_admin, f"Location {report_location} not found in admin table"
    assert "Anonymous Worker" in body_admin, "Anonymous shield not displayed in admin table"
    record("8. Submit Safety Report & Admin Ingestion", True, f"Report {test_ref_no} successfully submitted anonymously and rendered in Admin Queue")
except Exception as e:
    record("8. Submit Safety Report & Admin Ingestion", False, str(e))

# Audit 9: Admin Status Update (Open -> Under Review -> Resolved)
try:
    assert test_ref_no is not None
    # Extract report id
    req_admin = urllib.request.Request(f"{BASE_URL}/admin?industry=All")
    resp_admin = opener.open(req_admin)
    body_admin = resp_admin.read().decode("utf-8")
    
    match_id = re.search(test_ref_no + r'.*?action="/admin/safety-reports/(\d+)/update"', body_admin, re.DOTALL)
    if not match_id:
        match_id = re.search(r'action="/admin/safety-reports/(\d+)/update"', body_admin)
    assert match_id is not None, "Report ID not found in admin forms"
    rep_id = match_id.group(1)

    # Transition to Resolved
    data_update = urllib.parse.urlencode({
        "status": "Resolved",
        "admin_notes": "Audit Verified: Heavy latch installed and tested.",
        "industry_filter": "All"
    }).encode("utf-8")
    req_update = urllib.request.Request(f"{BASE_URL}/admin/safety-reports/{rep_id}/update", data=data_update)
    resp_update = opener.open(req_update)
    body_update = resp_update.read().decode("utf-8")
    assert resp_update.getcode() == 200
    assert f"Report #{rep_id} status updated to &#39;Resolved&#39;" in body_update or f"Report #{rep_id} status updated to 'Resolved'" in body_update

    # Check Public Tracking Route
    req_track = urllib.request.Request(f"{BASE_URL}/track/{test_ref_no}")
    resp_track = opener.open(req_track)
    body_track = resp_track.read().decode("utf-8")
    assert resp_track.getcode() == 200
    assert "Status: Resolved" in body_track
    assert "Heavy latch installed and tested." in body_track
    record("9. Admin Hazard Status Update & Public Tracker", True, f"Report #{rep_id} transitioned to Resolved with notes, confirmed on public tracker")
except Exception as e:
    record("9. Admin Hazard Status Update & Public Tracker", False, str(e))

# Audit 10: Admin Dashboard College Filter
try:
    req_col_admin = urllib.request.Request(f"{BASE_URL}/admin?industry=College")
    resp_col_admin = opener.open(req_col_admin)
    body_col_admin = resp_col_admin.read().decode("utf-8")
    assert resp_col_admin.getcode() == 200
    assert "College & Educational Support" in body_col_admin
    assert "Workforce Tracked" in body_col_admin
    record("10. Admin Dashboard - College Filter", True, "HTTP 200, College staff KPI cards and shift ledger verified")
except Exception as e:
    record("10. Admin Dashboard - College Filter", False, str(e))

print("\n=== Audit Summary ===")
passed = sum(1 for r in results if r["success"])
failed = sum(1 for r in results if not r["success"])
print(f"Total Tests: {len(results)} | Passed: {passed} | Failed: {failed}")

if failed > 0:
    sys.exit(1)
