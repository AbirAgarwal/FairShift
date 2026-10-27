# FairShift — Smart Workforce Management Platform

> **Hackathon MVP**: A lightweight, transparent workforce management system built for **Construction Trades** and **Higher Education Support Staff**.

---

## 📌 Problem & Impact

Manual workforce management on construction jobsites and university campuses causes:
1. **Unclear Salary Calculations**: Workers frequently experience missing overtime pay, ambiguous wage calculations, and confusing paper timesheets.
2. **Unreported Safety Hazards & Retaliation**: Frontline workers hesitate to report broken scaffolding, chemical ventilation problems, or lack of PPE due to fear of supervisor retaliation.
3. **Excessive Working Hours & Fatigue**: Unmonitored 10+ hour shifts cause severe physical exhaustion, leading to dangerous accidents and burn-out.
4. **Lost Credential Records**: Certifications (e.g. OSHA 30, Bloodborne Pathogens, Arc Flash) are scattered across paper cards and often lapse unnoticed.

**FairShift** solves this with an honest, transparent system providing clear wage calculations, tamper-evident hazard tracking, automated fatigue auditing with clear evidence, and portable skill passports.

---

## 🏗️ Supported Industries

1. **Construction Trades**:
   - Roles: Scaffolder, Heavy Equipment Operator, Journeyman Electrician, Mason, Safety Apprentice.
   - Hazard categories: Unsafe Scaffolding, Crane / Hydraulic Malfunction, Electrical Grounding, Silica Dust, Fall Hazards.
2. **College & Educational Support Staff**:
   - Roles: Facilities Janitorial Tech, Chemistry Lab Safety Assistant, Dining Hall Culinary Crew, Grounds & Snow Removal, Campus Night Escort.
   - Hazard categories: Chemical Fume Hood Exhaust, Floor Slip / Grease Spills, Biohazard Disposal, Extreme Weather Gear Shortage.

---

## 🚀 Key Features

### 1. Worker Portal (`/worker`)
- **Industry & Worker Switcher**: Instant switching between Construction and College demo workers.
- **Active Shift Clock-In & Clock-Out**: Live timestamping with status indicator. Supports fast demo shift simulation (8.0h standard, 9.5h overtime, 11.5h fatigue).
- **Manual Shift Entry**: Direct entry for past completed shifts to simulate timesheet migration.
- **Transparent Salary Calculator**: Live itemized breakdown showing standard pay, overtime pay (1.5x rate), and total estimated gross pay. Includes explicit wage transparency notice.
- **Retaliation-Free Hazard Reporting**: Submit hazards with category, location, severity, and an **identity shielding checkbox** that prevents worker IDs from being recorded or shown.
- **Instant Tracking Code**: Generates reference numbers (e.g., `HAZ-CON-8841`, `HAZ-COL-4011`).
- **Skill & Training Passport**: Real-time record of active, expiring, and valid certifications.
- **Confidential Feedback Voice**: Submit honest thoughts on scheduling fairness and workplace respect.

### 2. Employer / Admin Dashboard (`/admin`)
- **Executive KPI Cards**: Live counts of Active Staff, Shifts Logged, Overtime Hours, Open Hazards, and Fatigue Alerts.
- **Industry Sector Filtering**: Instant switching between All, Construction, and College staff.
- **Fatigue & Overtime Warning Center**: Automatically flags shifts exceeding safe duration with **clear evidence** (e.g. *"Shift exceeded 10.0h safety threshold (11.5h total). Physical and cognitive exhaustion probability is elevated"*), accompanied by recommended mitigation actions.
- **Hazard Incident Queue**: View all hazard tickets with severity badges. Update ticket status (`Open`, `Under Review`, `Resolved`) and add administrative action notes.
- **Attendance Ledger**: Searchable shift history with duration, overtime breakdown, and fatigue evaluations.
- **Anonymous Worker Pulse Feed**: View employee sentiment grouped by category with zero personal identifying information exposed.
- **Configurable Safety Thresholds**: Live controls to update standard shift limits (default 8.0h), fatigue trigger limits (default 10.0h), and overtime multiplier (default 1.5x).

### 3. Public / Worker Hazard Tracker (`/track`)
- Enter any reference code (e.g. `HAZ-CON-8841`) to view its three-stage resolution pipeline (`Open` &rarr; `Under Review` &rarr; `Resolved`), inspection timeline, and corrective actions while keeping worker identity strictly protected.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.13, Flask 3.1
- **Database**: SQLite with parameterized queries and foreign key constraints
- **Templates**: Jinja2 server-rendered HTML5
- **Styling**: Vanilla modern responsive CSS (Tailwind/Vercel aesthetic, no Node/npm build step required)
- **Production Server**: Gunicorn (for containerized deployment)
- **Testing**: `pytest` and Python `unittest`

Repository size: **< 1 MB** (Zero bulky assets, zero heavy frameworks).

---

## 💻 Local Quickstart

### 1. Prerequisites
- Python 3.10+ installed

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Automated Tests
```bash
python -m pytest tests/
# or
python -m unittest discover tests
```
*(All 18 unit and route integration tests will run and pass).*

### 4. Start the Application
```bash
python app.py
```
Open your browser to:
```
http://localhost:8080
```

---

## ☁️ Google Cloud Run Deployment

The application is pre-configured for Google Cloud Run:
- Listens on `0.0.0.0`
- Reads the `PORT` environment variable (defaults to `8080`)
- Includes a production `Dockerfile` with multi-threaded Gunicorn

### Deployment Commands

#### Step 1: Authenticate with Google Cloud
```bash
gcloud auth login
```

#### Step 2: Set your active Google Cloud Project
```bash
gcloud config set project YOUR_PROJECT_ID
```

#### Step 3: Enable required GCP Services
```bash
gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com run.googleapis.com
```

#### Step 4: Build and Submit Docker Container via Cloud Build
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/fairshift
```

#### Step 5: Deploy Service to Google Cloud Run
```bash
gcloud run deploy fairshift \
  --image gcr.io/YOUR_PROJECT_ID/fairshift \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars SECRET_KEY=fairshift-production-secure-key-2026
```

Once deployment completes, Cloud Run will print the live HTTPS URL (e.g., `https://fairshift-xxxxxx-uc.a.run.app`).

---

## 📋 Manual Steps Required by You

As an AI assistant, I have verified the code, initialized the SQLite database, and run all 18 unit/integration tests locally. You must perform the following steps in your personal environment:
1. **Google Cloud Account**: You must log in to your Google Cloud Console and ensure billing is enabled on your project.
2. **Google Cloud SDK**: Install the `gcloud` CLI if not already installed (`winget install Google.CloudSDK` on Windows).
3. **Run `gcloud auth login`**: Authorize your terminal session with your Google account.
4. **Deploy**: Run the `gcloud builds submit` and `gcloud run deploy` commands shown above.

---

## ⚖️ Fairness & Simulation Disclosures

- **Gross Pay Estimate**: Salary calculations compute estimated gross earnings using recorded hours and verified base wage rates. They do not factor in regional income taxes, healthcare premiums, or localized withholdings.
- **Simulated Demo Data**: Seed data provided in the database (Marcus Vance, Sarah Jenkins, etc.) are simulated archetypes representing realistic industry scenarios for demonstration purposes.
- **Anonymity Guarantee**: Anonymous hazard reports and feedback records are cryptographically detached from the worker table upon submission; no IP addresses or worker foreign keys are retained for anonymous entries.
