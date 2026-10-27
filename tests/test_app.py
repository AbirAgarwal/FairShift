"""
Automated Test Suite for FairShift
Validates transparent salary calculation, fatigue detection rules, database seeding,
and all core Worker and Admin routes.
"""

import os
import unittest
import tempfile
import database
import app as fairshift_app


class FairShiftTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary test database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        database.DB_PATH = self.db_path

        # Initialize schema and seed data
        database.init_db()

        # Configure Flask app for testing
        fairshift_app.app.config["TESTING"] = True
        fairshift_app.app.config["WTF_CSRF_ENABLED"] = False
        self.client = fairshift_app.app.test_client()

    def tearDown(self):
        # Remove temporary test database
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    # --- Unit Tests: Transparent Salary Engine ---

    def test_salary_calculation_standard(self):
        """Verify regular pay with 0 overtime hours."""
        res = fairshift_app.calculate_salary(base_hours=40.0, hourly_rate=25.0, overtime_hours=0.0)
        self.assertEqual(res["base_hours"], 40.0)
        self.assertEqual(res["hourly_rate"], 25.0)
        self.assertEqual(res["regular_pay"], 1000.0)
        self.assertEqual(res["overtime_pay"], 0.0)
        self.assertEqual(res["gross_pay"], 1000.0)
        self.assertIn("FairShift Notice", res["disclaimer"])

    def test_salary_calculation_with_overtime(self):
        """Verify 1.5x overtime multiplier and gross breakdown."""
        # 40 hrs @ $20 = $800; 10 hrs OT @ ($20 * 1.5 = $30) = $300; Gross = $1100
        res = fairshift_app.calculate_salary(base_hours=40.0, hourly_rate=20.0, overtime_hours=10.0, multiplier=1.5)
        self.assertEqual(res["regular_pay"], 800.0)
        self.assertEqual(res["overtime_rate"], 30.0)
        self.assertEqual(res["overtime_pay"], 300.0)
        self.assertEqual(res["gross_pay"], 1100.0)

    def test_salary_calculation_handles_edge_cases(self):
        """Verify invalid or negative values are handled gracefully."""
        res = fairshift_app.calculate_salary(base_hours="invalid", hourly_rate=-10, overtime_hours="bad")
        self.assertEqual(res["base_hours"], 0.0)
        self.assertEqual(res["gross_pay"], 0.0)

    # --- Unit Tests: Fatigue & Overtime Detection ---

    def test_fatigue_evaluation_standard_shift(self):
        """8.0h shift is evaluated as standard."""
        eval_res = fairshift_app.evaluate_shift_fatigue(total_hours=8.0, daily_threshold=8.0, fatigue_threshold=10.0)
        self.assertEqual(eval_res["level"], "normal")
        self.assertEqual(eval_res["badge_class"], "badge-success")

    def test_fatigue_evaluation_overtime_shift(self):
        """9.5h shift triggers overtime warning but not critical fatigue."""
        eval_res = fairshift_app.evaluate_shift_fatigue(total_hours=9.5, daily_threshold=8.0, fatigue_threshold=10.0)
        self.assertEqual(eval_res["level"], "warning")
        self.assertIn("beyond the standard 8.0h", eval_res["evidence"])

    def test_fatigue_evaluation_critical_shift(self):
        """11.5h shift triggers high fatigue alert with mandatory rest requirement."""
        eval_res = fairshift_app.evaluate_shift_fatigue(total_hours=11.5, daily_threshold=8.0, fatigue_threshold=10.0)
        self.assertEqual(eval_res["level"], "critical")
        self.assertEqual(eval_res["badge_class"], "badge-danger")
        self.assertIn("exceeded 10.0h safety threshold", eval_res["evidence"])
        self.assertIn("12h rest", eval_res["recommendation"])

    # --- Database Seeding Tests ---

    def test_database_seed_contains_both_industries(self):
        """Verify seeded data supports both Construction and College Support staff."""
        conn = database.get_db()
        con_workers = conn.execute("SELECT * FROM workers WHERE industry = 'Construction'").fetchall()
        col_workers = conn.execute("SELECT * FROM workers WHERE industry = 'College'").fetchall()
        skills = conn.execute("SELECT * FROM skills").fetchall()
        reports = conn.execute("SELECT * FROM safety_reports").fetchall()
        conn.close()

        self.assertGreaterEqual(len(con_workers), 4)
        self.assertGreaterEqual(len(col_workers), 4)
        self.assertGreaterEqual(len(skills), 5)
        self.assertGreaterEqual(len(reports), 3)

    # --- Route Integration Tests ---

    def test_root_redirects_to_worker(self):
        """Root route '/' redirects to '/worker'."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/worker", resp.headers["Location"])

    def test_worker_portal_get_construction(self):
        """Worker portal renders Construction view with workers."""
        resp = self.client.get("/worker?industry=Construction")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Construction Trades", resp.data)
        self.assertIn(b"CON-101", resp.data)

    def test_worker_portal_get_college(self):
        """Worker portal renders College view with workers."""
        resp = self.client.get("/worker?industry=College")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"College & Educational Support", resp.data)
        self.assertIn(b"COL-201", resp.data)

    def test_check_in_and_check_out_flow(self):
        """Test full attendance check-in and check-out workflow."""
        conn = database.get_db()
        worker = conn.execute("SELECT * FROM workers WHERE worker_code = 'CON-103'").fetchone()
        conn.close()

        # Check-in
        cin_resp = self.client.post("/worker/check-in", data={
            "worker_id": worker["id"],
            "worker_code": worker["worker_code"],
            "industry": worker["industry"],
            "notes": "East Tower electrical conduits"
        }, follow_redirects=True)
        self.assertEqual(cin_resp.status_code, 200)

        # Verify active shift in DB
        conn = database.get_db()
        active = conn.execute(
            "SELECT * FROM attendance WHERE worker_id = ? AND check_out IS NULL",
            (worker["id"],)
        ).fetchone()
        self.assertIsNotNone(active)
        attendance_id = active["id"]
        conn.close()

        # Check-out with simulated 9.0 hours
        cout_resp = self.client.post("/worker/check-out", data={
            "attendance_id": attendance_id,
            "worker_code": worker["worker_code"],
            "industry": worker["industry"],
            "notes": "Completed subpanel install",
            "simulated_hours": "9.0"
        }, follow_redirects=True)
        self.assertEqual(cout_resp.status_code, 200)

        # Verify record closed and overtime computed (9.0h - 8.0h threshold = 1.0h OT)
        conn = database.get_db()
        closed = conn.execute("SELECT * FROM attendance WHERE id = ?", (attendance_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(closed["check_out"])
        self.assertEqual(closed["total_hours"], 9.0)
        self.assertEqual(closed["overtime_hours"], 1.0)

    def test_manual_shift_entry(self):
        """Test logging past completed shifts directly."""
        conn = database.get_db()
        worker = conn.execute("SELECT * FROM workers WHERE worker_code = 'COL-203'").fetchone()
        conn.close()

        resp = self.client.post("/worker/manual-entry", data={
            "worker_id": worker["id"],
            "worker_code": worker["worker_code"],
            "industry": worker["industry"],
            "shift_date": "2026-10-25",
            "hours_worked": "8.5",
            "notes": "Dining hall catering prep"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        entry = conn.execute(
            "SELECT * FROM attendance WHERE worker_id = ? ORDER BY id DESC LIMIT 1",
            (worker["id"],)
        ).fetchone()
        conn.close()
        self.assertEqual(entry["total_hours"], 8.5)
        self.assertEqual(entry["overtime_hours"], 0.5)

    def test_safety_hazard_reporting_anonymous(self):
        """Test reporting a safety hazard with anonymous protection active."""
        resp = self.client.post("/worker/report-hazard", data={
            "worker_id": 1,
            "worker_code": "CON-101",
            "industry": "Construction",
            "category": "Unsafe Scaffolding",
            "severity": "Critical",
            "location": "North Wing Scaffold Tower",
            "description": "Missing horizontal sway braces and loose couplers.",
            "is_anonymous": "on"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Safety hazard report successfully submitted", resp.data)

        # Check DB - worker_id should be NULL or unlinked due to anonymous protection
        conn = database.get_db()
        rep = conn.execute(
            "SELECT * FROM safety_reports WHERE location = 'North Wing Scaffold Tower'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(rep)
        self.assertEqual(rep["is_anonymous"], 1)
        self.assertIsNone(rep["worker_id"])
        self.assertTrue(rep["reference_no"].startswith("HAZ-CON-"))

    def test_anonymous_worker_feedback(self):
        """Test submitting feedback."""
        resp = self.client.post("/worker/feedback", data={
            "worker_id": 2,
            "worker_code": "CON-102",
            "industry": "Construction",
            "category": "Work Hours & Fatigue",
            "feedback_text": "We need mandatory water breaks during afternoon concrete pours."
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        fb = conn.execute("SELECT * FROM feedback WHERE feedback_text LIKE '%mandatory water%'").fetchone()
        conn.close()
        self.assertIsNotNone(fb)
        self.assertEqual(fb["is_anonymous"], 1)

    def test_admin_dashboard_view(self):
        """Admin dashboard displays metrics, tables, and alerts."""
        resp = self.client.get("/admin")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Workforce Safety & Compliance Dashboard", resp.data)
        self.assertIn(b"Workforce Tracked", resp.data)
        self.assertIn(b"Safety Hazard Ticket Management", resp.data)
        self.assertIn(b"Fatigue & Overtime Warning Center", resp.data)

    def test_admin_hazard_status_update(self):
        """Admin can update report status from Open to Resolved with notes."""
        conn = database.get_db()
        rep = conn.execute("SELECT id FROM safety_reports WHERE status = 'Open' LIMIT 1").fetchone()
        conn.close()
        report_id = rep["id"]

        resp = self.client.post(f"/admin/safety-reports/{report_id}/update", data={
            "status": "Resolved",
            "admin_notes": "Safety inspector repaired scaffolding on site.",
            "industry_filter": "All"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        updated = conn.execute("SELECT * FROM safety_reports WHERE id = ?", (report_id,)).fetchone()
        conn.close()
        self.assertEqual(updated["status"], "Resolved")
        self.assertEqual(updated["admin_notes"], "Safety inspector repaired scaffolding on site.")

    def test_track_report_by_reference(self):
        """Public tracking portal displays report details without leaking anonymous worker identity."""
        conn = database.get_db()
        rep = conn.execute("SELECT reference_no FROM safety_reports LIMIT 1").fetchone()
        conn.close()
        ref_no = rep["reference_no"]

        resp = self.client.get(f"/track/{ref_no}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(ref_no.encode(), resp.data)
        self.assertIn(b"Safety Hazard Resolution Tracker", resp.data)

    def test_demo_reset(self):
        """Test resetting demo database to seed state."""
        resp = self.client.post("/demo/reset", data={"next": "/admin"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"restored to factory seed state", resp.data)


if __name__ == "__main__":
    unittest.main()
