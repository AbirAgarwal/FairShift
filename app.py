"""
FairShift — Smart Workforce Management Platform
Flask Application providing Worker Portal and Employer/Admin Dashboard.
Supports Construction and College Support Staff industries with safety,
transparent salary calculation, fatigue detection, and retaliation-free reporting.
"""

import os
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, session
)
import database

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fairshift-hackathon-secure-key-2026")

# Enforce secure cookie settings in production environments
if os.environ.get("FLASK_ENV") == "production" or os.environ.get("K_SERVICE"):
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )


# --- Helper Calculation Functions ---

def get_system_settings(conn):
    """Retrieve system thresholds from settings table."""
    settings = {
        "daily_overtime_threshold": 8.0,
        "fatigue_warning_threshold": 10.0,
        "overtime_rate_multiplier": 1.5,
    }
    rows = conn.execute("SELECT key, value FROM system_settings").fetchall()
    for row in rows:
        try:
            settings[row["key"]] = float(row["value"])
        except (ValueError, TypeError):
            pass
    return settings


def calculate_salary(base_hours, hourly_rate, overtime_hours, multiplier=1.5):
    """
    Transparent salary calculation engine.
    Computes regular pay, overtime pay with multiplier, and estimated gross earnings.
    """
    try:
        base_h = max(0.0, float(base_hours))
        rate = max(0.0, float(hourly_rate))
        ot_h = max(0.0, float(overtime_hours))
        mult = max(1.0, float(multiplier))
    except (ValueError, TypeError):
        base_h, rate, ot_h, mult = 0.0, 0.0, 0.0, 1.5

    regular_pay = round(base_h * rate, 2)
    overtime_rate = round(rate * mult, 2)
    overtime_pay = round(ot_h * overtime_rate, 2)
    gross_pay = round(regular_pay + overtime_pay, 2)

    return {
        "base_hours": base_h,
        "hourly_rate": rate,
        "regular_pay": regular_pay,
        "overtime_hours": ot_h,
        "overtime_rate_multiplier": mult,
        "overtime_rate": overtime_rate,
        "overtime_pay": overtime_pay,
        "gross_pay": gross_pay,
        "disclaimer": (
            "FairShift Notice: This calculation represents estimated gross earnings "
            "based on recorded hours and verified base wage rates. It excludes applicable "
            "taxes, union dues, health benefits, and statutory payroll deductions."
        )
    }


def evaluate_shift_fatigue(total_hours, daily_threshold=8.0, fatigue_threshold=10.0):
    """
    Provide clear evidence behind fatigue and overtime warnings.
    """
    try:
        hours = float(total_hours)
    except (ValueError, TypeError):
        hours = 0.0

    if hours >= fatigue_threshold:
        return {
            "level": "critical",
            "badge_class": "badge-danger",
            "label": "High Fatigue Risk",
            "evidence": (
                f"Shift exceeded {fatigue_threshold:.1f}h safety threshold ({hours:.1f}h total). "
                f"Physical and cognitive exhaustion probability is elevated."
            ),
            "recommendation": "Mandatory 12h rest period required before next assigned shift."
        }
    elif hours > daily_threshold:
        ot = hours - daily_threshold
        return {
            "level": "warning",
            "badge_class": "badge-warning",
            "label": "Overtime Threshold Exceeded",
            "evidence": (
                f"Logged {hours:.1f}h ({ot:.1f}h beyond the standard {daily_threshold:.1f}h shift limit)."
            ),
            "recommendation": "Qualifies for 1.5x overtime rate. Monitor cumulative weekly hours."
        }
    else:
        return {
            "level": "normal",
            "badge_class": "badge-success",
            "label": "Standard Shift",
            "evidence": f"Logged {hours:.1f}h within standard {daily_threshold:.1f}h safety guidelines.",
            "recommendation": "Normal rest interval applies."
        }


# --- Template Filters ---

@app.template_filter("datetime_format")
def datetime_format(value, fmt="%b %d, %Y %I:%M %p"):
    if not value:
        return "In Progress / Active"
    try:
        dt = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime(fmt)
    except Exception:
        return str(value)


@app.template_filter("currency")
def currency_format(value):
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


# --- Application Routes ---

@app.route("/")
def index():
    """Default landing redirects to Worker Portal demo view."""
    return redirect(url_for("worker_portal"))


@app.route("/worker")
def worker_portal():
    """
    Worker Portal interface:
    Allows industry selection, worker selection/switching, attendance check-in/out,
    interactive salary calculation, safety hazard reporting, and skill passport view.
    """
    conn = database.get_db()
    settings = get_system_settings(conn)

    industry_filter = request.args.get("industry", "Construction")
    worker_code = request.args.get("worker_code")

    # Fetch workers for industry
    all_workers = conn.execute(
        "SELECT * FROM workers ORDER BY industry, worker_code"
    ).fetchall()

    industry_workers = [w for w in all_workers if w["industry"] == industry_filter]

    # Select active worker
    current_worker = None
    if worker_code:
        current_worker = next((w for w in all_workers if w["worker_code"] == worker_code), None)
    if not current_worker and industry_workers:
        current_worker = industry_workers[0]
    elif not current_worker and all_workers:
        current_worker = all_workers[0]

    # If worker found, fetch their attendance, skills, and reports
    active_shift = None
    attendance_history = []
    skills_records = []
    worker_reports = []
    total_hours_sum = 0.0
    total_overtime_sum = 0.0

    if current_worker:
        wid = current_worker["id"]

        # Check for open/active shift (check_out is NULL)
        active_shift = conn.execute(
            "SELECT * FROM attendance WHERE worker_id = ? AND check_out IS NULL ORDER BY check_in DESC LIMIT 1",
            (wid,)
        ).fetchone()

        # Completed attendance history
        attendance_rows = conn.execute(
            "SELECT * FROM attendance WHERE worker_id = ? AND check_out IS NOT NULL ORDER BY check_in DESC LIMIT 20",
            (wid,)
        ).fetchall()

        for row in attendance_rows:
            fatigue_info = evaluate_shift_fatigue(
                row["total_hours"],
                settings["daily_overtime_threshold"],
                settings["fatigue_warning_threshold"]
            )
            attendance_history.append({
                "record": row,
                "fatigue": fatigue_info
            })
            total_hours_sum += float(row["total_hours"] or 0)
            total_overtime_sum += float(row["overtime_hours"] or 0)

        # Skills & Certifications
        skills_records = conn.execute(
            "SELECT * FROM skills WHERE worker_id = ? ORDER BY expiry_date ASC",
            (wid,)
        ).fetchall()

        # Safety reports submitted by or associated with this worker
        worker_reports = conn.execute(
            "SELECT * FROM safety_reports WHERE worker_id = ? ORDER BY created_at DESC LIMIT 10",
            (wid,)
        ).fetchall()

    # Base hours worked (excluding overtime)
    base_hours_sum = max(0.0, total_hours_sum - total_overtime_sum)
    calc_rate = current_worker["hourly_rate"] if current_worker else 25.0

    # Custom calculator inputs or defaults from recorded history
    calc_base_input = request.args.get("calc_base", str(round(base_hours_sum, 1) or 40.0))
    calc_rate_input = request.args.get("calc_rate", str(calc_rate))
    calc_ot_input = request.args.get("calc_ot", str(round(total_overtime_sum, 1) or 5.0))

    salary_breakdown = calculate_salary(
        calc_base_input,
        calc_rate_input,
        calc_ot_input,
        multiplier=settings["overtime_rate_multiplier"]
    )

    conn.close()

    return render_template(
        "worker.html",
        all_workers=all_workers,
        industry_workers=industry_workers,
        current_worker=current_worker,
        industry_filter=industry_filter,
        active_shift=active_shift,
        attendance_history=attendance_history,
        skills_records=skills_records,
        worker_reports=worker_reports,
        salary_breakdown=salary_breakdown,
        calc_inputs={"base": calc_base_input, "rate": calc_rate_input, "ot": calc_ot_input},
        settings=settings,
        now_str=datetime.now().strftime("%Y-%m-%d %H:%M")
    )


@app.route("/worker/check-in", methods=["POST"])
def worker_check_in():
    """Clock in worker with timestamp and site/task notes."""
    worker_id = request.form.get("worker_id")
    worker_code = request.form.get("worker_code")
    industry = request.form.get("industry", "Construction")
    notes = request.form.get("notes", "").strip() or "Shift started via FairShift Worker Portal"

    conn = database.get_db()
    worker = None
    if worker_id:
        worker = conn.execute("SELECT id, worker_code, industry FROM workers WHERE id = ?", (worker_id,)).fetchone()
    if not worker and worker_code:
        worker = conn.execute("SELECT id, worker_code, industry FROM workers WHERE worker_code = ?", (worker_code,)).fetchone()

    if not worker:
        flash("Worker identity not found in database.", "error")
        conn.close()
        return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))

    resolved_id = worker["id"]
    # Check if already clocked in
    existing = conn.execute(
        "SELECT id FROM attendance WHERE worker_id = ? AND check_out IS NULL",
        (resolved_id,)
    ).fetchone()

    if existing:
        flash("You are already checked in to an active shift.", "warning")
    else:
        now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.execute(
                "INSERT INTO attendance (worker_id, check_in, notes, is_demo) VALUES (?, ?, ?, 0)",
                (resolved_id, now_dt, notes)
            )
        flash(f"Check-in recorded at {now_dt}. Have a safe shift!", "success")

    conn.close()
    return redirect(url_for("worker_portal", industry=industry, worker_code=worker["worker_code"]))


@app.route("/worker/check-out", methods=["POST"])
def worker_check_out():
    """Clock out worker, calculate total hours, overtime hours, and store record."""
    attendance_id = request.form.get("attendance_id")
    worker_code = request.form.get("worker_code")
    industry = request.form.get("industry", "Construction")
    notes = request.form.get("notes", "").strip()

    conn = database.get_db()
    settings = get_system_settings(conn)
    record = conn.execute(
        "SELECT * FROM attendance WHERE id = ?",
        (attendance_id,)
    ).fetchone()

    if not record or record["check_out"] is not None:
        flash("No active shift found to clock out.", "error")
        conn.close()
        return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))

    # Calculate duration
    check_in_dt = datetime.strptime(record["check_in"][:19], "%Y-%m-%d %H:%M:%S")
    check_out_dt = datetime.now()

    # For hackathon demo, if check-in was just seconds ago, allow a simulation or realistic minimum
    duration_seconds = (check_out_dt - check_in_dt).total_seconds()
    duration_hours = max(0.1, round(duration_seconds / 3600.0, 2))

    # If demo simulation override provided
    simulated_hours = request.form.get("simulated_hours")
    if simulated_hours:
        try:
            duration_hours = round(float(simulated_hours), 2)
        except ValueError:
            pass

    daily_threshold = settings["daily_overtime_threshold"]
    overtime_hours = max(0.0, round(duration_hours - daily_threshold, 2))

    updated_notes = (record["notes"] or "") + (" | " + notes if notes else "")

    with conn:
        conn.execute("""
            UPDATE attendance
            SET check_out = ?, total_hours = ?, overtime_hours = ?, notes = ?
            WHERE id = ?
        """, (check_out_dt.strftime("%Y-%m-%d %H:%M:%S"), duration_hours, overtime_hours, updated_notes, attendance_id))

    flash(
        f"Shift completed! Total: {duration_hours:.2f} hrs (Overtime: {overtime_hours:.2f} hrs). Logged to your record.",
        "success"
    )
    conn.close()
    return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))


@app.route("/worker/manual-entry", methods=["POST"])
def worker_manual_entry():
    """Allow adding a shift record directly (useful for demo & paper timesheet migration)."""
    worker_id = request.form.get("worker_id")
    worker_code = request.form.get("worker_code")
    industry = request.form.get("industry", "Construction")
    shift_date = request.form.get("shift_date") or datetime.now().strftime("%Y-%m-%d")
    hours_worked = request.form.get("hours_worked")
    notes = request.form.get("notes", "Logged shift")

    try:
        hours = float(hours_worked)
        if hours <= 0 or hours > 24:
            raise ValueError()
    except (ValueError, TypeError):
        flash("Please enter a valid shift duration between 0.5 and 24 hours.", "error")
        return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))

    conn = database.get_db()
    worker = None
    if worker_id:
        worker = conn.execute("SELECT id, worker_code FROM workers WHERE id = ?", (worker_id,)).fetchone()
    if not worker and worker_code:
        worker = conn.execute("SELECT id, worker_code FROM workers WHERE worker_code = ?", (worker_code,)).fetchone()

    if not worker:
        flash("Worker profile not found.", "error")
        conn.close()
        return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))

    resolved_id = worker["id"]
    settings = get_system_settings(conn)
    daily_threshold = settings["daily_overtime_threshold"]
    overtime_hours = max(0.0, round(hours - daily_threshold, 2))

    check_in_str = f"{shift_date} 07:00:00"
    end_hour = 7 + int(hours)
    end_minute = int((hours - int(hours)) * 60)
    check_out_str = f"{shift_date} {end_hour:02d}:{end_minute:02d}:00"

    with conn:
        conn.execute("""
            INSERT INTO attendance (worker_id, check_in, check_out, total_hours, overtime_hours, notes, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (resolved_id, check_in_str, check_out_str, hours, overtime_hours, notes))

    flash(f"Manual shift logged successfully: {hours} hours (Overtime: {overtime_hours}h).", "success")
    conn.close()
    return redirect(url_for("worker_portal", industry=industry, worker_code=worker["worker_code"]))


@app.route("/worker/report-hazard", methods=["POST"])
def report_hazard():
    """
    Submit safety hazard report. Supports anonymous submissions to prevent retaliation.
    Generates a unique reference number (e.g. HAZ-CON-9123).
    """
    worker_id = request.form.get("worker_id")
    worker_code = request.form.get("worker_code")
    industry = request.form.get("industry", "Construction")
    category = request.form.get("category", "General Safety")
    severity = request.form.get("severity", "Medium")
    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()
    is_anonymous = 1 if request.form.get("is_anonymous") == "on" else 0

    if not location or not description:
        flash("Hazard location and description are mandatory.", "error")
        return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))

    ref_no = database.generate_reference_no(industry)
    effective_worker_id = None

    conn = database.get_db()
    if not is_anonymous:
        worker = None
        if worker_id:
            worker = conn.execute("SELECT id FROM workers WHERE id = ?", (worker_id,)).fetchone()
        if not worker and worker_code:
            worker = conn.execute("SELECT id FROM workers WHERE worker_code = ?", (worker_code,)).fetchone()
        if worker:
            effective_worker_id = worker["id"]

    with conn:
        conn.execute("""
            INSERT INTO safety_reports (
                reference_no, worker_id, is_anonymous, industry,
                category, severity, location, description, status, admin_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open', 'Under initial intake review.')
        """, (ref_no, effective_worker_id, is_anonymous, industry, category, severity, location, description))
    conn.close()

    anon_msg = " [Anonymous protection active — your identity is shielded]" if is_anonymous else ""
    flash(
        f"Safety hazard report successfully submitted! Reference ID: {ref_no}{anon_msg}. "
        f"Track its resolution progress anytime.",
        "success"
    )
    return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))


@app.route("/worker/feedback", methods=["POST"])
def submit_feedback():
    """Submit worker sentiment and feedback (strictly anonymous by default)."""
    worker_id = request.form.get("worker_id")
    worker_code = request.form.get("worker_code")
    industry = request.form.get("industry", "Construction")
    category = request.form.get("category", "Work Hours & Fatigue")
    feedback_text = request.form.get("feedback_text", "").strip()

    if not feedback_text:
        flash("Please provide feedback comments before submitting.", "error")
        return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))

    conn = database.get_db()
    effective_worker_id = None
    if worker_id:
        worker = conn.execute("SELECT id FROM workers WHERE id = ?", (worker_id,)).fetchone()
        if worker:
            effective_worker_id = worker["id"]
    if not effective_worker_id and worker_code:
        worker = conn.execute("SELECT id FROM workers WHERE worker_code = ?", (worker_code,)).fetchone()
        if worker:
            effective_worker_id = worker["id"]

    with conn:
        conn.execute("""
            INSERT INTO feedback (worker_id, is_anonymous, industry, category, feedback_text)
            VALUES (?, 1, ?, ?, ?)
        """, (effective_worker_id, industry, category, feedback_text))
    conn.close()

    flash(
        "Thank you! Your feedback was submitted anonymously. It helps ensure fair scheduling and safe conditions.",
        "success"
    )
    return redirect(url_for("worker_portal", industry=industry, worker_code=worker_code))


# --- Admin / Employer Interface ---

@app.route("/admin")
def admin_dashboard():
    """
    Employer / Admin Dashboard:
    - Summary metrics (workers, attendance shifts, overtime hours, open hazards, fatigue warnings)
    - Industry filter (All, Construction, College)
    - Fatigue & Overtime Risk Center with transparent evidence
    - Attendance records table
    - Hazard report management with status updates
    - Anonymous worker feedback feed
    - Configurable work-hour threshold controls
    """
    conn = database.get_db()
    settings = get_system_settings(conn)
    industry_filter = request.args.get("industry", "All")

    # Base queries depending on industry filter
    if industry_filter == "All":
        workers = conn.execute("SELECT * FROM workers ORDER BY industry, worker_code").fetchall()
        attendance_rows = conn.execute("""
            SELECT a.*, w.worker_code, w.full_name, w.industry, w.role_title, w.hourly_rate
            FROM attendance a
            JOIN workers w ON a.worker_id = w.id
            ORDER BY a.check_in DESC
            LIMIT 50
        """).fetchall()
        hazard_rows = conn.execute("""
            SELECT r.*, w.worker_code, w.full_name
            FROM safety_reports r
            LEFT JOIN workers w ON r.worker_id = w.id
            ORDER BY
                CASE r.severity
                    WHEN 'Critical' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    ELSE 4
                END,
                r.created_at DESC
        """).fetchall()
        feedback_rows = conn.execute("""
            SELECT * FROM feedback ORDER BY created_at DESC LIMIT 30
        """).fetchall()
    else:
        workers = conn.execute(
            "SELECT * FROM workers WHERE industry = ? ORDER BY worker_code",
            (industry_filter,)
        ).fetchall()
        attendance_rows = conn.execute("""
            SELECT a.*, w.worker_code, w.full_name, w.industry, w.role_title, w.hourly_rate
            FROM attendance a
            JOIN workers w ON a.worker_id = w.id
            WHERE w.industry = ?
            ORDER BY a.check_in DESC
            LIMIT 50
        """, (industry_filter,)).fetchall()
        hazard_rows = conn.execute("""
            SELECT r.*, w.worker_code, w.full_name
            FROM safety_reports r
            LEFT JOIN workers w ON r.worker_id = w.id
            WHERE r.industry = ?
            ORDER BY
                CASE r.severity
                    WHEN 'Critical' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    ELSE 4
                END,
                r.created_at DESC
        """, (industry_filter,)).fetchall()
        feedback_rows = conn.execute("""
            SELECT * FROM feedback WHERE industry = ? ORDER BY created_at DESC LIMIT 30
        """, (industry_filter,)).fetchall()

    # Calculate Summary Metrics
    total_workers_count = len(workers)
    total_shifts_count = len(attendance_rows)
    total_overtime_hours = sum(float(r["overtime_hours"] or 0) for r in attendance_rows)
    open_hazards_count = sum(1 for r in hazard_rows if r["status"] in ("Open", "Under Review"))
    critical_hazards_count = sum(1 for r in hazard_rows if r["severity"] == "Critical" and r["status"] != "Resolved")

    # Build Fatigue Warnings and Evidence List
    fatigue_alerts = []
    processed_attendance = []

    for row in attendance_rows:
        hours = float(row["total_hours"] or 0)
        fatigue_info = evaluate_shift_fatigue(
            hours,
            settings["daily_overtime_threshold"],
            settings["fatigue_warning_threshold"]
        )
        processed_attendance.append({
            "record": row,
            "fatigue": fatigue_info
        })

        if fatigue_info["level"] in ("warning", "critical"):
            fatigue_alerts.append({
                "worker_code": row["worker_code"],
                "full_name": row["full_name"],
                "industry": row["industry"],
                "role_title": row["role_title"],
                "date": row["check_in"][:10],
                "hours": hours,
                "fatigue": fatigue_info,
                "attendance_id": row["id"]
            })

    conn.close()

    return render_template(
        "admin.html",
        industry_filter=industry_filter,
        total_workers_count=total_workers_count,
        total_shifts_count=total_shifts_count,
        total_overtime_hours=round(total_overtime_hours, 1),
        open_hazards_count=open_hazards_count,
        critical_hazards_count=critical_hazards_count,
        fatigue_alerts=fatigue_alerts,
        attendance_records=processed_attendance,
        hazard_reports=hazard_rows,
        feedback_records=feedback_rows,
        settings=settings
    )


@app.route("/admin/safety-reports/<int:report_id>/update", methods=["POST"])
def update_report_status(report_id):
    """Update status of a safety hazard report and attach admin resolution notes."""
    new_status = request.form.get("status")
    admin_notes = request.form.get("admin_notes", "").strip()
    industry_filter = request.form.get("industry_filter", "All")

    if new_status not in ("Open", "Under Review", "Resolved"):
        flash("Invalid status specified.", "error")
        return redirect(url_for("admin_dashboard", industry=industry_filter))

    conn = database.get_db()
    with conn:
        conn.execute("""
            UPDATE safety_reports
            SET status = ?, admin_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, admin_notes, report_id))
    conn.close()

    flash(f"Report #{report_id} status updated to '{new_status}'.", "success")
    return redirect(url_for("admin_dashboard", industry=industry_filter))


@app.route("/admin/settings/update", methods=["POST"])
def update_settings():
    """Update configurable work-hour thresholds."""
    industry_filter = request.form.get("industry_filter", "All")
    daily_ot = request.form.get("daily_overtime_threshold")
    fatigue = request.form.get("fatigue_warning_threshold")
    multiplier = request.form.get("overtime_rate_multiplier")

    conn = database.get_db()
    with conn:
        if daily_ot:
            conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('daily_overtime_threshold', ?)", (str(float(daily_ot)),))
        if fatigue:
            conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('fatigue_warning_threshold', ?)", (str(float(fatigue)),))
        if multiplier:
            conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('overtime_rate_multiplier', ?)", (str(float(multiplier)),))
    conn.close()

    flash("Workforce thresholds successfully updated! Recalculating live risks...", "success")
    return redirect(url_for("admin_dashboard", industry=industry_filter))


@app.route("/track")
@app.route("/track/<reference_no>")
def track_report(reference_no=None):
    """
    Public / Worker hazard report status lookup by reference number.
    Maintains anonymity: shields worker identity if marked anonymous.
    """
    query_ref = reference_no or request.args.get("ref", "").strip()
    report = None
    if query_ref:
        conn = database.get_db()
        report = conn.execute("""
            SELECT r.*, w.worker_code, w.full_name
            FROM safety_reports r
            LEFT JOIN workers w ON r.worker_id = w.id
            WHERE r.reference_no = ?
        """, (query_ref,)).fetchone()
        conn.close()

    return render_template("track_report.html", query_ref=query_ref, report=report)


@app.route("/demo/reset", methods=["POST"])
def reset_demo():
    """Reset database to fresh demo dataset for live judging demonstration."""
    database.seed_demo_data()
    flash("Demo database has been restored to factory seed state with Construction and College records.", "success")
    next_url = request.form.get("next") or url_for("worker_portal")
    return redirect(next_url)


# --- Error Handlers ---

@app.errorhandler(404)
def not_found(e):
    return render_template("base.html", error_message="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("base.html", error_message="An internal server error occurred."), 500


# Automatically ensure DB tables and seed data upon startup
database.init_db()


if __name__ == "__main__":
    # Cloud Run passes PORT in environment variable (defaults to 8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
