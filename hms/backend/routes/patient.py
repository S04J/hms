from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.models import db, Patient, Doctor, Appointment, Department, DoctorAvailability, User
from datetime import date, timedelta, datetime
from functools import wraps
import csv, io

patient_bp = Blueprint('patient', __name__, url_prefix='/api/patient')


def patient_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        if get_jwt().get('role') != 'patient':
            return jsonify({'error': 'Patient access required'}), 403
        return f(*args, **kwargs)
    return decorated


def get_current_patient():
    user_id = int(get_jwt_identity())
    return Patient.query.filter_by(user_id=user_id).first()


#Dashboard

@patient_bp.route('/dashboard', methods=['GET'])
@patient_required
def dashboard():
    patient = get_current_patient()
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404

    today = date.today()
    departments = Department.query.all()

    upcoming = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.date >= today,
        Appointment.status == 'Booked'
    ).order_by(Appointment.date.asc()).all()

    past = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.status == 'Completed'
    ).order_by(Appointment.date.desc()).limit(10).all()

    return jsonify({
        'patient': patient.to_dict(),
        'departments': [d.to_dict() for d in departments],
        'upcoming_appointments': [a.to_dict() for a in upcoming],
        'past_appointments': [a.to_dict() for a in past],
    })


#Profile

@patient_bp.route('/profile', methods=['PUT'])
@patient_required
def update_profile():
    patient = get_current_patient()
    data = request.get_json(silent=True) or {}
    try:
        patient.full_name        = data.get('full_name',        patient.full_name)
        patient.phone            = data.get('phone',            patient.phone)
        patient.address          = data.get('address',          patient.address)
        patient.gender           = data.get('gender',           patient.gender)
        patient.blood_group      = data.get('blood_group',      patient.blood_group)
        patient.emergency_contact = data.get('emergency_contact', patient.emergency_contact)

        dob_str = data.get('date_of_birth')
        if dob_str:
            try:
                patient.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if data.get('email'):
            patient.user.email = data['email']

        db.session.commit()
        return jsonify(patient.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


#Departments 

@patient_bp.route('/departments', methods=['GET'])
@jwt_required()
def list_departments():
    departments = Department.query.all()
    result = []
    for d in departments:
        d_dict = d.to_dict()
        
        doctors = Doctor.query.filter_by(department_id=d.id).all()
        d_dict['doctors'] = [
            doc.to_dict() for doc in doctors
            if not doc.user.is_blacklisted
        ]
        result.append(d_dict)
    return jsonify(result)


#Doctor search

@patient_bp.route('/doctors/search', methods=['GET'])
@jwt_required()
def search_doctors():
    q              = request.args.get('q', '').strip()
    specialization = request.args.get('specialization', '').strip()

    query = Doctor.query.join(User).filter(User.is_blacklisted == False)  # noqa

    if q:
        query = query.filter(
            (Doctor.full_name.ilike(f'%{q}%')) |
            (Doctor.specialization.ilike(f'%{q}%'))
        )
    if specialization:
        query = query.filter(Doctor.specialization.ilike(f'%{specialization}%'))

    return jsonify([d.to_dict() for d in query.all()])


#Doctor availability

@patient_bp.route('/doctors/<int:doctor_id>/availability', methods=['GET'])
@jwt_required()
def doctor_availability(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404

    today    = date.today()
    week_end = today + timedelta(days=7)

    avails = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.date >= today,
        DoctorAvailability.date <= week_end,
        DoctorAvailability.is_available == True,  # noqa
    ).order_by(DoctorAvailability.date.asc()).all()

    result = []
    for avail in avails:
        a = avail.to_dict()
        
        morning_booked = Appointment.query.filter_by(
            doctor_id=doctor_id, date=avail.date, time_slot='morning', status='Booked'
        ).count()
        evening_booked = Appointment.query.filter_by(
            doctor_id=doctor_id, date=avail.date, time_slot='evening', status='Booked'
        ).count()
        a['morning_available'] = avail.morning_available and (morning_booked == 0)
        a['evening_available'] = avail.evening_available and (evening_booked == 0)
        result.append(a)

    return jsonify({'doctor': doctor.to_dict(), 'availability': result})


#Book appointment

@patient_bp.route('/appointments', methods=['POST'])
@patient_required
def book_appointment():
    patient = get_current_patient()
    data    = request.get_json(silent=True) or {}

    doctor_id   = data.get('doctor_id')
    date_str    = data.get('date', '')
    time_slot   = data.get('time_slot', '').lower().strip()

    if not all([doctor_id, date_str, time_slot]):
        return jsonify({'error': 'doctor_id, date and time_slot are required'}), 400

    if time_slot not in ('morning', 'evening'):
        return jsonify({'error': 'time_slot must be "morning" or "evening"'}), 400

    try:
        apt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    if apt_date < date.today():
        return jsonify({'error': 'Cannot book past appointments'}), 400


    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404

    
    avail = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id, date=apt_date, is_available=True
    ).first()
    if not avail:
        return jsonify({'error': 'Doctor is not available on this date'}), 400

    
    if time_slot == 'morning' and not avail.morning_available:
        return jsonify({'error': 'Doctor morning slot is not available'}), 400
    if time_slot == 'evening' and not avail.evening_available:
        return jsonify({'error': 'Doctor evening slot is not available'}), 400

    
    slot_taken = Appointment.query.filter_by(
        doctor_id=doctor_id, date=apt_date, time_slot=time_slot, status='Booked'
    ).first()
    if slot_taken:
        return jsonify({'error': 'This time slot is already booked by another patient'}), 409

    # Prevent same patient booking same doctor same day twice
    already_booked = Appointment.query.filter_by(
        patient_id=patient.id, doctor_id=doctor_id, date=apt_date, status='Booked'
    ).first()
    if already_booked:
        return jsonify({'error': 'You already have an appointment with this doctor on this date'}), 409

    try:
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor_id,
            date=apt_date,
            time_slot=time_slot,
            visit_type=data.get('visit_type', 'In-person'),
            status='Booked',
            notes=data.get('notes', ''),
        )
        db.session.add(appointment)
        db.session.commit()
        return jsonify(appointment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


#Cancel appointment

@patient_bp.route('/appointments/<int:apt_id>/cancel', methods=['PUT'])
@patient_required
def cancel_appointment(apt_id):
    patient = get_current_patient()
    apt = Appointment.query.filter_by(id=apt_id, patient_id=patient.id).first()
    if not apt:
        return jsonify({'error': 'Appointment not found'}), 404
    if apt.status != 'Booked':
        return jsonify({'error': 'Only booked appointments can be cancelled'}), 400
    try:
        apt.status = 'Cancelled'
        db.session.commit()
        return jsonify(apt.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


#Reschedule appointment

@patient_bp.route('/appointments/<int:apt_id>/reschedule', methods=['PUT'])
@patient_required
def reschedule_appointment(apt_id):
    patient = get_current_patient()
    apt = Appointment.query.filter_by(id=apt_id, patient_id=patient.id).first()
    if not apt:
        return jsonify({'error': 'Appointment not found'}), 404
    if apt.status != 'Booked':
        return jsonify({'error': 'Only booked appointments can be rescheduled'}), 400

    data = request.get_json(silent=True) or {}
    new_date_str = data.get('date', '')
    new_slot     = data.get('time_slot', '').lower().strip()

    if not new_date_str or not new_slot:
        return jsonify({'error': 'date and time_slot are required'}), 400

    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    if new_date < date.today():
        return jsonify({'error': 'Cannot reschedule to a past date'}), 400

    slot_taken = Appointment.query.filter(
        Appointment.doctor_id == apt.doctor_id,
        Appointment.date == new_date,
        Appointment.time_slot == new_slot,
        Appointment.status == 'Booked',
        Appointment.id != apt_id,       
    ).first()
    if slot_taken:
        return jsonify({'error': 'That slot is already booked'}), 409

    try:
        apt.date      = new_date
        apt.time_slot = new_slot
        db.session.commit()
        return jsonify(apt.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


#Treatment history 

@patient_bp.route('/history', methods=['GET'])
@patient_required
def history():
    patient = get_current_patient()
    apts = Appointment.query.filter_by(
        patient_id=patient.id, status='Completed'
    ).order_by(Appointment.date.desc()).all()
    return jsonify([a.to_dict() for a in apts])


#Export CSV 

@patient_bp.route('/export-csv', methods=['POST'])
@patient_required
def export_csv():
    patient = get_current_patient()

   
    try:
        from backend.tasks import export_patient_csv
        task = export_patient_csv.delay(patient.id, patient.user.email)
        return jsonify({
            'message': 'Export started. You will receive an email when ready.',
            'task_id': task.id
        })
    except Exception:
        pass

    
    apts = Appointment.query.filter_by(
        patient_id=patient.id, status='Completed'
    ).order_by(Appointment.date.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Visit No', 'Patient Name', 'Doctor', 'Department',
        'Date', 'Time Slot', 'Visit Type', 'Tests Done',
        'Diagnosis', 'Prescription', 'Medicines', 'Notes', 'Next Visit'
    ])
    for i, apt in enumerate(apts, 1):
        t = apt.treatment
        writer.writerow([
            i,
            patient.full_name,
            apt.doctor.full_name if apt.doctor else '',
            apt.doctor.department.name if apt.doctor and apt.doctor.department else '',
            apt.date.isoformat(),
            apt.time_slot,
            apt.visit_type,
            t.tests_done   if t else '',
            t.diagnosis    if t else '',
            t.prescription if t else '',
            t.medicines    if t else '',
            t.doctor_notes if t else '',
            t.next_visit.isoformat() if t and t.next_visit else '',
        ])
    return jsonify({'csv': output.getvalue(), 'message': 'Export ready'})
