import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_caching import Cache

from backend.config import config
from backend.models import db, User, Department, Doctor, DoctorAvailability
from backend.routes.auth import auth_bp
from backend.routes.admin import admin_bp
from backend.routes.doctor import doctor_bp
from backend.routes.patient import patient_bp

cache = Cache()
jwt = JWTManager()


def create_app(config_name='default'):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FRONTEND_DIST = os.path.join(BASE_DIR, 'frontend', 'dist')
    
    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path='')
    app.config.from_object(config[config_name])

    
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, origins='*', supports_credentials=True)

    try:
        cache.init_app(app)
    except Exception:
        app.config['CACHE_TYPE'] = 'SimpleCache'
        cache.init_app(app)

    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)

    
    try:
        from backend.tasks import make_celery, register_tasks
        celery = make_celery(app)
        register_tasks(celery, app)
        app.celery = celery
    except Exception as e:
        print(f"Celery setup skipped: {e}")

    
    with app.app_context():
        db.create_all()
        _seed_data(app)

    
    _setup_scheduler(app)

    # Serve Vue frontend - catch-all for SPA
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path.startswith('api/'):
            return jsonify({'error': 'Not found'}), 404
        static_file = os.path.join(FRONTEND_DIST, path) if path else ''
        if path and os.path.isfile(static_file):
            return send_from_directory(FRONTEND_DIST, path)
        index_path = os.path.join(FRONTEND_DIST, 'index.html')
        if os.path.isfile(index_path):
            return send_from_directory(FRONTEND_DIST, 'index.html')
        return 'Frontend not found. Ensure frontend/dist/index.html exists.', 500

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'Internal server error'}), 500

    return app


def _seed_data(app):
    
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(
            username=app.config['ADMIN_USERNAME'],
            email=app.config['ADMIN_EMAIL'],
            role='admin'
        )
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)

    departments = ['Cardiology', 'Oncology', 'General', 'Neurology', 'Orthopedics', 'Pediatrics', 'Dermatology']
    descs = {
        'Cardiology': 'Specialized in heart and cardiovascular diseases.',
        'Oncology': 'Diagnosis, treatment, and care of patients with cancer.',
        'General': 'General medicine and primary healthcare services.',
        'Neurology': 'Disorders of the nervous system.',
        'Orthopedics': 'Musculoskeletal system, bones and joints.',
        'Pediatrics': 'Medical care for infants, children, and adolescents.',
        'Dermatology': 'Skin, hair, and nail conditions.'
    }
    for name in departments:
        if not Department.query.filter_by(name=name).first():
            dept = Department(name=name, description=descs.get(name, ''))
            db.session.add(dept)

    db.session.commit()


def _setup_scheduler(app):
    import threading
    from datetime import datetime

    _fired = {"daily": None, "monthly": None}

    def _tick():
        while True:
            try:
                now = datetime.now()
                today_key = now.strftime("%Y-%m-%d")
                month_key  = now.strftime("%Y-%m")

                if now.hour == 8 and now.minute == 0 and _fired["daily"] != today_key:
                    _fired["daily"] = today_key
                    _run_daily_reminders(app)

                if now.day == 1 and now.hour == 7 and now.minute == 0 and _fired["monthly"] != month_key:
                    _fired["monthly"] = month_key
                    _run_monthly_report(app)

            except Exception as exc:
                print(f"[Scheduler] tick error: {exc}")

            threading.Event().wait(60)

    t = threading.Thread(target=_tick, daemon=True, name="hms-scheduler")
    t.start()
    print("[Scheduler] Background scheduler started (daily reminders 08:00, monthly reports on 1st).")


def _run_daily_reminders(app):
    with app.app_context():
        try:
            from backend.tasks import send_daily_reminders
            send_daily_reminders.delay()
        except Exception as e:
            print(f"Daily reminders error: {e}")


def _run_monthly_report(app):
    with app.app_context():
        try:
            from backend.tasks import send_monthly_report
            send_monthly_report.delay()
        except Exception as e:
            print(f"Monthly report error: {e}")


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
