"""
FairShift - Database Management and Schema
Provides SQLite connection management, schema initialization, and demo data seeding.
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.environ.get("FAIRSHIFT_DB_PATH", "fairshift.db")


def get_db():
    """Get a database connection configured with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all required tables if they don't exist and ensure initial seed data."""
    conn = get_db()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_code TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            industry TEXT NOT NULL, -- 'Construction' or 'College'
            role_title TEXT NOT NULL,
            hourly_rate REAL NOT NULL DEFAULT 22.0,
            phone TEXT,
            is_demo BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            check_in TIMESTAMP NOT NULL,
            check_out TIMESTAMP,
            total_hours REAL DEFAULT 0.0,
            overtime_hours REAL DEFAULT 0.0,
            notes TEXT,
            is_demo BOOLEAN NOT NULL DEFAULT 0,
            FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS safety_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_no TEXT UNIQUE NOT NULL,
            worker_id INTEGER,
            is_anonymous BOOLEAN NOT NULL DEFAULT 0,
            industry TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL, -- 'Low', 'Medium', 'High', 'Critical'
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open', -- 'Open', 'Under Review', 'Resolved'
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            certification TEXT NOT NULL,
            issuing_body TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            expiry_date TEXT,
            status TEXT NOT NULL DEFAULT 'Valid', -- 'Valid', 'Expiring Soon', 'Expired'
            FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            is_anonymous BOOLEAN NOT NULL DEFAULT 1,
            industry TEXT NOT NULL,
            category TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # Default settings for fatigue / overtime
        conn.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('daily_overtime_threshold', '8.0')")
        conn.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('fatigue_warning_threshold', '10.0')")
        conn.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('overtime_rate_multiplier', '1.5')")

    conn.close()

    # Seed demo data if database was just created
    seed_demo_data_if_empty()


def seed_demo_data_if_empty():
    """Seed sample records if workers table has 0 rows."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM workers")
    row = cursor.fetchone()
    if row and row["count"] == 0:
        seed_demo_data(conn)
    conn.close()


def seed_demo_data(conn=None):
    """Seed realistic, clearly labeled demo records for Construction and College industries."""
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True

    with conn:
        # Clear existing demo data
        conn.execute("DELETE FROM feedback")
        conn.execute("DELETE FROM skills")
        conn.execute("DELETE FROM safety_reports")
        conn.execute("DELETE FROM attendance")
        conn.execute("DELETE FROM workers")

        demo_workers = [
            # Construction Industry
            ("CON-101", "Marcus Vance", "Construction", "Scaffold Supervisor & Master Carpenter", 34.50, "(555) 234-5601", 1),
            ("CON-102", "Elena Rostova", "Construction", "Heavy Equipment Operator (Crane & Loader)", 38.00, "(555) 234-5602", 1),
            ("CON-103", "David Kim", "Construction", "Certified Journeyman Electrician", 36.25, "(555) 234-5603", 1),
            ("CON-104", "Mateo Fernandez", "Construction", "Structural Mason & Concrete Finisher", 28.50, "(555) 234-5604", 1),
            ("CON-105", "Aaliyah Brooks", "Construction", "Site Safety Coordinator & Apprentice", 26.00, "(555) 234-5605", 1),
            # College & Educational Institution Support Staff
            ("COL-201", "Sarah Jenkins", "College", "Lead Campus Facilities Janitorial Tech", 22.50, "(555) 876-1201", 1),
            ("COL-202", "Robert Chen", "College", "Biochemistry Teaching Lab Assistant & Safety Tech", 25.00, "(555) 876-1202", 1),
            ("COL-203", "Maria Morales", "College", "Dining Hall Cook & Culinary Operations", 21.00, "(555) 876-1203", 1),
            ("COL-204", "James 'Jim' Wilson", "College", "Groundskeeping & Heavy Snow Removal Specialist", 23.50, "(555) 876-1204", 1),
            ("COL-205", "Priya Patel", "College", "Campus Night Escort & Residence Patrol Officer", 24.25, "(555) 876-1205", 1),
        ]

        for code, name, ind, role, rate, phone, is_demo in demo_workers:
            conn.execute("""
                INSERT INTO workers (worker_code, full_name, industry, role_title, hourly_rate, phone, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (code, name, ind, role, rate, phone, is_demo))

        # Fetch inserted IDs
        workers_map = {}
        for row in conn.execute("SELECT id, worker_code, industry FROM workers"):
            workers_map[row["worker_code"]] = (row["id"], row["industry"])

        # Seed Skills Passport records
        skills_data = [
            ("CON-101", "OSHA 30 Construction Safety", "Certification", "Occupational Safety & Health Admin", "2024-03-15", "2027-03-15", "Valid"),
            ("CON-101", "Suspended Scaffold Operations", "License", "Building Trades Safety Council", "2023-08-10", "2026-11-01", "Expiring Soon"),
            ("CON-101", "First Aid, CPR & AED", "Certification", "American Red Cross", "2025-01-20", "2027-01-20", "Valid"),
            
            ("CON-102", "NCCCO Mobile Crane Operator", "License", "National Commission for Cert of Crane Operators", "2023-05-12", "2028-05-12", "Valid"),
            ("CON-102", "Heavy Rigging & Signalperson", "Certification", "NCCCO", "2024-02-18", "2027-02-18", "Valid"),

            ("CON-103", "NFPA 70E Arc Flash Safety", "Certification", "National Fire Protection Assoc", "2024-06-11", "2027-06-11", "Valid"),
            ("CON-103", "Lockout/Tagout (LOTO) Specialist", "Qualification", "Industrial Safety Board", "2023-10-04", "2026-10-04", "Valid"),

            ("CON-104", "Silica Dust Hazard Awareness", "Certification", "OSHA Directorate of Training", "2024-04-10", "2026-10-15", "Expiring Soon"),
            ("CON-104", "Confined Space Entry", "Certification", "Safety Training Institute", "2025-02-01", "2028-02-01", "Valid"),

            ("CON-105", "Fall Protection Competent Person", "Certification", "Safety Institute of North America", "2024-09-01", "2026-09-01", "Valid"),

            # College Staff Skills
            ("COL-201", "Bloodborne Pathogens & Biohazard Cleaning", "Certification", "OSHA Health & Safety Division", "2024-08-20", "2027-08-20", "Valid"),
            ("COL-201", "Chemical Sanitization Protocols (EPA List N)", "Qualification", "National Environmental Health Assoc", "2023-11-14", "2026-11-14", "Valid"),

            ("COL-202", "Chemical Hygiene & Fume Hood Maintenance", "Certification", "Campus Safety & Risk Management", "2024-01-10", "2027-01-10", "Valid"),
            ("COL-202", "Hazardous Waste Handling & Spill Kit Mgmt", "Certification", "EPA Resource Conservation", "2023-09-15", "2026-09-15", "Valid"),

            ("COL-203", "ServSafe Food Protection Manager", "Certification", "National Restaurant Association", "2023-07-22", "2028-07-22", "Valid"),
            ("COL-203", "Commercial Kitchen Fire & Suppression Safety", "Certification", "State Fire Marshal Office", "2024-05-18", "2027-05-18", "Valid"),

            ("COL-204", "Commercial Zero-Turn & Tractor Operations", "License", "State Turf & Landscape Assoc", "2023-04-15", "2026-04-15", "Valid"),
            ("COL-204", "Storm Cleanup Chainsaw Safety Certified", "Certification", "OSHA Tree Care Academy", "2024-11-03", "2027-11-03", "Valid"),

            ("COL-205", "Campus Clery Act & Title IX First Responder", "Certification", "National Association of Campus Safety", "2024-03-01", "2027-03-01", "Valid"),
            ("COL-205", "De-escalation & Mental Health First Aid", "Certification", "National Council for Mental Wellbeing", "2025-01-15", "2027-01-15", "Valid"),
        ]

        for code, sname, cert, issuer, isdate, exdate, st in skills_data:
            wid = workers_map[code][0]
            conn.execute("""
                INSERT INTO skills (worker_id, skill_name, certification, issuing_body, issue_date, expiry_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (wid, sname, cert, issuer, isdate, exdate, st))

        # Seed Attendance with realistic hours and some intentional overtime/fatigue flags for demonstration!
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        three_days_ago = now - timedelta(days=3)

        # Helper to compute hours
        def format_dt(dt):
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        attendance_records = [
            # Marcus Vance (Construction) - 8.5 hours shift yesterday (0.5h overtime)
            (
                workers_map["CON-101"][0],
                format_dt(yesterday.replace(hour=7, minute=0, second=0)),
                format_dt(yesterday.replace(hour=15, minute=30, second=0)),
                8.5, 0.5, "Scaffold framing assembly - Sector C", 1
            ),
            # Marcus Vance - 8.0h shift 2 days ago
            (
                workers_map["CON-101"][0],
                format_dt(two_days_ago.replace(hour=7, minute=0, second=0)),
                format_dt(two_days_ago.replace(hour=15, minute=0, second=0)),
                8.0, 0.0, "Routine safety walk & plank anchoring", 1
            ),
            # Elena Rostova (Construction) - EXCESSIVE FATIGUE SHIFT: 11.5 hours! Exceeds 10h threshold
            (
                workers_map["CON-102"][0],
                format_dt(yesterday.replace(hour=6, minute=0, second=0)),
                format_dt(yesterday.replace(hour=17, minute=30, second=0)),
                11.5, 3.5, "Urgent concrete pour crane operation (High Fatigue Alert)", 1
            ),
            (
                workers_map["CON-102"][0],
                format_dt(two_days_ago.replace(hour=6, minute=30, second=0)),
                format_dt(two_days_ago.replace(hour=15, minute=30, second=0)),
                9.0, 1.0, "Steel beam placement on 4th floor", 1
            ),
            # David Kim (Construction) - 8.0h standard shift
            (
                workers_map["CON-103"][0],
                format_dt(yesterday.replace(hour=8, minute=0, second=0)),
                format_dt(yesterday.replace(hour=16, minute=30, second=0)),
                8.5, 0.5, "Subpanel wiring and grounding inspection", 1
            ),
            # Mateo Fernandez (Construction) - 10.5 hours! Another fatigue warning
            (
                workers_map["CON-104"][0],
                format_dt(two_days_ago.replace(hour=7, minute=0, second=0)),
                format_dt(two_days_ago.replace(hour=17, minute=30, second=0)),
                10.5, 2.5, "Foundation slab curing and nighttime smoothing", 1
            ),
            # Sarah Jenkins (College) - 8.0h shift
            (
                workers_map["COL-201"][0],
                format_dt(yesterday.replace(hour=6, minute=0, second=0)),
                format_dt(yesterday.replace(hour=14, minute=30, second=0)),
                8.5, 0.5, "Science Center main lecture hall sanitation", 1
            ),
            (
                workers_map["COL-201"][0],
                format_dt(two_days_ago.replace(hour=6, minute=0, second=0)),
                format_dt(two_days_ago.replace(hour=14, minute=0, second=0)),
                8.0, 0.0, "Quad administrative restrooms deep clean", 1
            ),
            # Robert Chen (College) - 9.5 hours
            (
                workers_map["COL-202"][0],
                format_dt(yesterday.replace(hour=8, minute=0, second=0)),
                format_dt(yesterday.replace(hour=17, minute=30, second=0)),
                9.5, 1.5, "Assisted chem lab extended research prep & waste audit", 1
            ),
            # James Wilson (College) - EXCESSIVE FATIGUE SHIFT: 12.0 hours during winter storm prep
            (
                workers_map["COL-204"][0],
                format_dt(yesterday.replace(hour=4, minute=0, second=0)),
                format_dt(yesterday.replace(hour=16, minute=0, second=0)),
                12.0, 4.0, "Emergency snowfall salting & sidewalk clearing (High Fatigue Alert)", 1
            ),
            # Priya Patel (College) - Night shift 8.0h
            (
                workers_map["COL-205"][0],
                format_dt(yesterday.replace(hour=22, minute=0, second=0)),
                format_dt(now.replace(hour=6, minute=0, second=0)),
                8.0, 0.0, "Dormitory perimeter patrol & security check", 1
            )
        ]

        for wid, cin, cout, tot, ot, notes, is_demo in attendance_records:
            conn.execute("""
                INSERT INTO attendance (worker_id, check_in, check_out, total_hours, overtime_hours, notes, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (wid, cin, cout, tot, ot, notes, is_demo))

        # Seed Safety Hazard Reports
        safety_data = [
            (
                "HAZ-CON-8841",
                workers_map["CON-101"][0],
                0, # Not anonymous
                "Construction",
                "Unsafe Scaffolding",
                "Critical",
                "Building B, East Elevation (Level 5)",
                "Guardrail is loose and two wooden toe-boards are missing near the debris chute. High fall danger in high wind conditions.",
                "Open",
                "Assigned to site safety officer. Barricade erected around East Elevation pending repair."
            ),
            (
                "HAZ-CON-8912",
                workers_map["CON-102"][0],
                1, # Anonymous to prevent retaliation
                "Construction",
                "Equipment Malfunction",
                "High",
                "Excavation Pit A - Caterpillar 330",
                "Hydraulic line shows micro-tears and is leaking fluid near the primary boom pivot. Poses sudden boom drop hazard.",
                "Under Review",
                "Mechanic scheduled for 2:00 PM inspection. Machine tagged Out-of-Service."
            ),
            (
                "HAZ-CON-8620",
                workers_map["CON-103"][0],
                0,
                "Construction",
                "Electrical Hazard",
                "Medium",
                "Temporary Power Board #3, Floor 2",
                "GFCI breaker tripped multiple times due to rain ingress through open window frame.",
                "Resolved",
                "Weatherproof NEMA-4 box installed; lines dried and tested clear by J. Electrician."
            ),
            (
                "HAZ-COL-4011",
                workers_map["COL-202"][0],
                0,
                "College",
                "Chemical Exposure / Fume Hood",
                "High",
                "Curie Hall Chemistry Lab 304",
                "Exhaust ventilation alarm is buzzing periodically; face velocity dropped below 60 FPM during organic solvent transfer.",
                "Under Review",
                "HVAC technicians contacted. Lab professors notified to halt volatile solvent usage."
            ),
            (
                "HAZ-COL-4055",
                workers_map["COL-201"][0],
                1, # Anonymous
                "College",
                "Slip / Trip Hazard",
                "Medium",
                "Dining Hall West Service Corridor",
                "Grease trap drain overflow during peak lunch hour. Floor tile is extremely slippery with inadequate warning signage.",
                "Open",
                "Janitorial slip warning cones placed. Facilities plumbing ticket #8949 opened."
            ),
            (
                "HAZ-COL-3980",
                workers_map["COL-204"][0],
                0,
                "College",
                "Lack of PPE / Equipment",
                "Low",
                "Facilities Maintenance Workshop Bay 2",
                "Supply of heavy duty thermal gloves for outdoor grounds staff was depleted during the freeze.",
                "Resolved",
                "Two cases of Class 2 thermal protective gloves received and restocked."
            )
        ]

        for ref, wid, anon, ind, cat, sev, loc, desc, st, anotes in safety_data:
            conn.execute("""
                INSERT INTO safety_reports (reference_no, worker_id, is_anonymous, industry, category, severity, location, description, status, admin_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ref, wid, anon, ind, cat, sev, loc, desc, st, anotes))

        # Seed Anonymous Worker Feedback
        feedback_data = [
            (
                workers_map["CON-101"][0], 1, "Construction", "Work Hours & Fatigue",
                "Last week we worked back-to-back 11-hour shifts for the concrete pour. Workers were noticeably exhausted handling heavy rebar. We need mandatory rotation relief on high heat days."
            ),
            (
                workers_map["CON-104"][0], 1, "Construction", "Pay Transparency",
                "The overtime breakdown on FairShift is a huge relief. Previously on paper timesheets, weekend 1.5x differential was often miscalculated or delayed by payroll."
            ),
            (
                workers_map["COL-201"][0], 1, "College", "Workplace Climate & Respect",
                "Appreciate having a platform to report broken elevator equipment without fear of friction with departmental supervisors. Support staff voices deserve to be taken seriously."
            ),
            (
                workers_map["COL-203"][0], 1, "College", "Work Hours & Fatigue",
                "During homecoming weekend, kitchen shifts stretched over 10 hours without sufficient break coverage. FairShift's fatigue flag helps management see our actual workload."
            ),
            (
                workers_map["COL-204"][0], 1, "College", "Safety Equipment",
                "Good response on the cold weather gear request. Clear hazard ticket tracking lets us know when maintenance items are actually resolved."
            )
        ]

        for wid, anon, ind, cat, txt in feedback_data:
            conn.execute("""
                INSERT INTO feedback (worker_id, is_anonymous, industry, category, feedback_text)
                VALUES (?, ?, ?, ?, ?)
            """, (wid, anon, ind, cat, txt))

    if close_after:
        conn.close()


def generate_reference_no(industry="Construction"):
    """Generate a clean, professional unique hazard tracking reference number."""
    prefix = "HAZ-CON" if industry == "Construction" else "HAZ-COL"
    random_digits = random.randint(1000, 9999)
    return f"{prefix}-{random_digits}"
