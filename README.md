# hms
A full-stack Hospital Management System built with Flask, Vue.js, SQLite, Redis, and Celery.

Tech Stack
Backend: Flask (REST API)
Frontend: Vue.js 3 (CDN), Bootstrap 5
Database: SQLite via Flask-SQLAlchemy
Caching: Redis via Flask-Caching
Background Jobs: Celery + APScheduler
Auth: JWT (Flask-JWT-Extended)
Project Structure
hms/
├── app.py                  # Main Flask application
├── run.py                  # Easy startup script
├── celery_worker.py        # Celery configuration
├── requirements.txt        # Python dependencies
├── backend/
│   ├── config.py           # App configuration
│   ├── models.py           # SQLAlchemy models
│   ├── tasks.py            # Celery background tasks
│   └── routes/
│       ├── auth.py         # Login/Register APIs
│       ├── admin.py        # Admin APIs
│       ├── doctor.py       # Doctor APIs
│       └── patient.py      # Patient APIs
└── frontend/
    ├── index.html          # Vue.js SPA entry point
    └── dist/               # Built frontend (auto-generated)
Setup & Run
1. Install Dependencies
pip install -r requirements.txt --break-system-packages
2. Start Redis (required for caching & Celery)
redis-server
3. Run Flask Application
python run.py
# or
python app.py
Access at: http://localhost:5000

4. (Optional) Start Celery Worker for Background Jobs
# In a new terminal:
celery -A celery_worker.celery worker --loglevel=info

# For periodic tasks (daily reminders, monthly reports):
celery -A celery_worker.celery beat --loglevel=info
Default Credentials
Role	Username	Password
Admin	admin	admin123
Doctor	(created by admin)	doctor123
Patient	(self-register)	-
API Endpoints
Authentication
POST /api/auth/login - Login
POST /api/auth/register - Patient registration
GET /api/auth/me - Current user info
Admin (requires admin JWT)
GET /api/admin/dashboard - Stats overview
GET/POST /api/admin/doctors - List/Create doctors
PUT /api/admin/doctors/<id> - Update doctor
DELETE /api/admin/doctors/<id> - Delete doctor
POST /api/admin/doctors/<id>/blacklist - Toggle blacklist
GET/PUT /api/admin/patients - Manage patients
POST /api/admin/patients/<id>/blacklist - Toggle blacklist
GET /api/admin/appointments - All appointments
GET /api/admin/search?q=&type= - Search
GET/POST /api/admin/departments - Manage departments
Doctor (requires doctor JWT)
GET /api/doctor/dashboard - Dashboard data
GET /api/doctor/appointments - All appointments
PUT /api/doctor/appointments/<id>/status - Update status
POST /api/doctor/appointments/<id>/treatment - Add/update treatment
GET /api/doctor/patients/<id>/history - Patient history
GET/POST /api/doctor/availability - Manage availability
Patient (requires patient JWT)
GET /api/patient/dashboard - Dashboard
PUT /api/patient/profile - Update profile
GET /api/patient/departments - All departments
GET /api/patient/doctors/search?q= - Search doctors
GET /api/patient/doctors/<id>/availability - Doctor availability
POST /api/patient/appointments - Book appointment
PUT /api/patient/appointments/<id>/cancel - Cancel
PUT /api/patient/appointments/<id>/reschedule - Reschedule
GET /api/patient/history - Treatment history
POST /api/patient/export-csv - Export CSV
Background Jobs
Daily Reminders (8:00 AM): Sends email/GChat reminders for appointments
Monthly Reports (1st of each month, 7:00 AM): Sends activity report to doctors
CSV Export (user-triggered async): Generates and emails treatment history CSV
Configuration (Environment Variables)
SECRET_KEY=your-secret
JWT_SECRET_KEY=your-jwt-secret
REDIS_HOST=localhost
REDIS_PORT=6379
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=hms@hospital.com
GCHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/.../messages?key=...
Features
Role-based access control (Admin, Doctor, Patient)
JWT authentication
Admin: Manage doctors, patients, appointments, departments
Doctor: View appointments, update treatment, set availability
Patient: Book/cancel/reschedule appointments, view history
Prevent duplicate bookings
Redis caching with expiry
Celery background jobs
Daily appointment reminders (email + Google Chat)
Monthly activity reports for doctors
Patient treatment history CSV export
Blacklist/unblacklist users
Search functionality
Responsive Bootstrap 5 UI
SQLite database (programmatically created)
Admin pre-seeded on startup
