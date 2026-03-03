from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.models import db, Doctor, DoctorAvailability, Appointment, Treatment, Patient
from datetime import date, timedelta, datetime
from functools import wraps

doctor_bp = Blueprint('doctor', __name__, url_prefix='/api/doctor')


def doctor_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        if get_jwt().get('role') != 'doctor':
            return jsonify({'error': 'Doctor access required'}), 403
        return f(*args, **kwargs)
    return decorated


def get_current_doctor():
    user_id = int(get_jwt_identity())
    return Doctor.query.filter_by(user_id=user_id).first()


#Dashboard

@doctor_bp.route('/dashboard', methods=['GET'])
@doctor_required
def dashboard():
    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404

    today    = date.today()
    week_end = today + timedelta(days=7)

    today_apts = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.date == today,
        Appointment.status != 'Cancelled'
    ).all()

    week_apts = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.date >= today,
        Appointment.date <= week_end,
        Appointment.status != 'Cancelled'
    ).order_by(Appointment.date.asc()).all()

    # Unique patients from week appointments (guard against empty list)
    patient_ids = list({a.patient_id for a in week_apts})
    patients = Patient.query.filter(Patient.id.in_(patient_ids)).all() if patient_ids else []

    return jsonify({
        'doctor': doctor.to_dict(),
        'today_appointments': [a.to_dict() for a in today_apts],
        'week_appointments':  [a.to_dict() for a in week_apts],
        'assigned_patients':  [p.to_dict() for p in patients],
    })


# ── Appointments ─────────────────────────────────────────────────────────────

@doctor_bp.route('/appointments', methods=['GET'])
@doctor_required
def appointments():
    doctor = get_current_doctor()
    status = request.args.get('status')
    q = Appointment.query.filter_by(doctor_id=doctor.id)
    if status:
        q = q.filter_by(status=status)
    return jsonify([a.to_dict() for a in q.order_by(Appointment.date.desc()).all()])


@doctor_bp.route('/appointments/<int:apt_id>/status', methods=['PUT'])
@doctor_required
def update_appointment_status(apt_id):
    doctor = get_current_doctor()
    apt = Appointment.query.filter_by(id=apt_id, doctor_id=doctor.id).first()
    if not apt:
        return jsonify({'error': 'Appointment not found'}), 404
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    if new_status not in ('Completed', 'Cancelled'):
        return jsonify({'error': 'Status must be Completed or Cancelled'}), 400
    try:
        apt.status = new_status
        db.session.commit()
        return jsonify(apt.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── Treatment ─────────────────────────────────────────────────────────────────

@doctor_bp.route('/appointments/<int:apt_id>/treatment', methods=['POST', 'PUT'])
@doctor_required
def update_treatment(apt_id):
    doctor = get_current_doctor()
    apt = Appointment.query.filter_by(id=apt_id, doctor_id=doctor.id).first()
    if not apt:
        return jsonify({'error': 'Appointment not found'}), 404

    data = request.get_json(silent=True) or {}
    try:
        if not apt.treatment:
            treatment = Treatment(appointment_id=apt_id)
            db.session.add(treatment)
            db.session.flush()
        else:
            treatment = apt.treatment

        treatment.diagnosis    = data.get('diagnosis',    treatment.diagnosis)
        treatment.prescription = data.get('prescription', treatment.prescription)
        treatment.medicines    = data.get('medicines',    treatment.medicines)
        treatment.tests_done   = data.get('tests_done',   treatment.tests_done)
        treatment.doctor_notes = data.get('doctor_notes', treatment.doctor_notes)

        next_visit_str = data.get('next_visit')
        if next_visit_str:
            try:
                treatment.next_visit = datetime.strptime(next_visit_str, '%Y-%m-%d').date()
            except ValueError:
                pass  # ignore bad date format

        apt.status = 'Completed'
        db.session.commit()
        return jsonify(treatment.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── Patient history (from doctor perspective) ─────────────────────────────────

@doctor_bp.route('/patients/<int:patient_id>/history', methods=['GET'])
@doctor_required
def patient_history(patient_id):
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    apts = Appointment.query.filter_by(
        patient_id=patient_id, status='Completed'
    ).order_by(Appointment.date.desc()).all()
    return jsonify({'patient': patient.to_dict(), 'appointments': [a.to_dict() for a in apts]})


# ── Availability ──────────────────────────────────────────────────────────────

@doctor_bp.route('/availability', methods=['GET'])
@doctor_required
def get_availability():
    doctor   = get_current_doctor()
    today    = date.today()
    week_end = today + timedelta(days=7)
    avails   = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date >= today,
        DoctorAvailability.date <= week_end,
    ).order_by(DoctorAvailability.date.asc()).all()
    return jsonify([a.to_dict() for a in avails])


@doctor_bp.route('/availability', methods=['POST'])
@doctor_required
def set_availability():
    doctor = get_current_doctor()
    data   = request.get_json(silent=True) or {}
    avail_list = data.get('availabilities', [])

    try:
        for item in avail_list:
            avail_date = datetime.strptime(item['date'], '%Y-%m-%d').date()

            existing = DoctorAvailability.query.filter_by(
                doctor_id=doctor.id, date=avail_date
            ).first()

            morning_sel = item.get('morning_selected', False)
            evening_sel = item.get('evening_selected', False)

            # Use defaults if frontend sends None/null for time strings
            m_start = item.get('morning_start') or '08:00'
            m_end   = item.get('morning_end')   or '12:00'
            e_start = item.get('evening_start') or '16:00'
            e_end   = item.get('evening_end')   or '21:00'

            if existing:
                existing.morning_available = morning_sel
                existing.evening_available = evening_sel
                existing.morning_start = m_start
                existing.morning_end   = m_end
                existing.evening_start = e_start
                existing.evening_end   = e_end
                existing.is_available  = morning_sel or evening_sel
            else:
                avail = DoctorAvailability(
                    doctor_id=doctor.id,
                    date=avail_date,
                    morning_start=m_start,
                    morning_end=m_end,
                    evening_start=e_start,
                    evening_end=e_end,
                    morning_available=morning_sel,
                    evening_available=evening_sel,
                    is_available=morning_sel or evening_sel,
                )
                db.session.add(avail)

        db.session.commit()
        return jsonify({'message': 'Availability saved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
