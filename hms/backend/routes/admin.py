from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from backend.models import db, User, Doctor, Patient, Department, Appointment, Treatment
from datetime import datetime
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        if get_jwt().get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    return jsonify({
        'total_doctors':       Doctor.query.count(),
        'total_patients':      Patient.query.count(),
        'total_appointments':  Appointment.query.count(),
        'booked_appointments': Appointment.query.filter_by(status='Booked').count(),
        'completed_appointments': Appointment.query.filter_by(status='Completed').count(),
        'cancelled_appointments': Appointment.query.filter_by(status='Cancelled').count(),
    })


#Doctors
@admin_bp.route('/doctors', methods=['GET'])
@admin_required
def list_doctors():
    return jsonify([d.to_dict() for d in Doctor.query.all()])


@admin_bp.route('/doctors', methods=['POST'])
@admin_required
def create_doctor():
    data = request.get_json(silent=True) or {}
    username  = data.get('username', '').strip()
    email     = data.get('email', '').strip()
    password  = data.get('password', 'doctor123') or 'doctor123'
    full_name = data.get('full_name', '').strip()

    if not all([username, email, full_name]):
        return jsonify({'error': 'username, email and full_name are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    try:
        user = User(username=username, email=email, role='doctor')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        
        dept_id = data.get('department_id')
        if not dept_id:
            dept_name = data.get('department_name', '').strip()
            if dept_name:
                dept = Department.query.filter_by(name=dept_name).first()
                if not dept:
                    dept = Department(name=dept_name,
                                      description=data.get('department_description', ''))
                    db.session.add(dept)
                    db.session.flush()
                dept_id = dept.id

        doctor = Doctor(
            user_id=user.id,
            full_name=full_name,
            specialization=data.get('specialization', ''),
            qualification=data.get('qualification', ''),
            experience_years=int(data.get('experience_years') or 0),
            bio=data.get('bio', ''),
            phone=data.get('phone', ''),
            department_id=dept_id or None,
        )
        db.session.add(doctor)
        db.session.commit()
        return jsonify(doctor.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not create doctor: {str(e)}'}), 500


@admin_bp.route('/doctors/<int:doctor_id>', methods=['PUT'])
@admin_required
def update_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404

    data = request.get_json(silent=True) or {}
    try:
        doctor.full_name       = data.get('full_name', doctor.full_name)
        doctor.specialization  = data.get('specialization', doctor.specialization)
        doctor.qualification   = data.get('qualification', doctor.qualification)
        doctor.experience_years = int(data.get('experience_years') or doctor.experience_years or 0)
        doctor.bio             = data.get('bio', doctor.bio)
        doctor.phone           = data.get('phone', doctor.phone)
        if data.get('department_id') is not None:
            doctor.department_id = data['department_id'] or None
        if data.get('email'):
            doctor.user.email = data['email']
        db.session.commit()
        return jsonify(doctor.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/doctors/<int:doctor_id>', methods=['DELETE'])
@admin_required
def delete_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    try:
        user = doctor.user
        db.session.delete(user)  
        db.session.commit()
        return jsonify({'message': 'Doctor deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/doctors/<int:doctor_id>/blacklist', methods=['POST'])
@admin_required
def blacklist_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    doctor.user.is_blacklisted = not doctor.user.is_blacklisted
    db.session.commit()
    status = 'blacklisted' if doctor.user.is_blacklisted else 'unblacklisted'
    return jsonify({'message': f'Doctor {status}', 'is_blacklisted': doctor.user.is_blacklisted})


#Patients

@admin_bp.route('/patients', methods=['GET'])
@admin_required
def list_patients():
    return jsonify([p.to_dict() for p in Patient.query.all()])


@admin_bp.route('/patients/<int:patient_id>', methods=['PUT'])
@admin_required
def update_patient(patient_id):
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    data = request.get_json(silent=True) or {}
    try:
        patient.full_name   = data.get('full_name',   patient.full_name)
        patient.phone       = data.get('phone',        patient.phone)
        patient.address     = data.get('address',      patient.address)
        patient.blood_group = data.get('blood_group',  patient.blood_group)
        if data.get('email'):
            patient.user.email = data['email']
        db.session.commit()
        return jsonify(patient.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/patients/<int:patient_id>/blacklist', methods=['POST'])
@admin_required
def blacklist_patient(patient_id):
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    patient.user.is_blacklisted = not patient.user.is_blacklisted
    db.session.commit()
    status = 'blacklisted' if patient.user.is_blacklisted else 'unblacklisted'
    return jsonify({'message': f'Patient {status}', 'is_blacklisted': patient.user.is_blacklisted})


#Appointments

@admin_bp.route('/appointments', methods=['GET'])
@admin_required
def list_appointments():
    apts = Appointment.query.order_by(Appointment.date.desc()).all()
    return jsonify([a.to_dict() for a in apts])


#Search

@admin_bp.route('/search', methods=['GET'])
@admin_required
def search():
    q           = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')
    results     = {}

    if search_type in ('all', 'doctor'):
        doctors = Doctor.query.filter(
            (Doctor.full_name.ilike(f'%{q}%')) |
            (Doctor.specialization.ilike(f'%{q}%'))
        ).all()
        results['doctors'] = [d.to_dict() for d in doctors]

    if search_type in ('all', 'patient'):
        patients = Patient.query.filter(
            (Patient.full_name.ilike(f'%{q}%')) |
            (Patient.phone.ilike(f'%{q}%'))
        ).all()
        results['patients'] = [p.to_dict() for p in patients]

    return jsonify(results)


#Departments

@admin_bp.route('/departments', methods=['GET'])
@admin_required
def list_departments():
    return jsonify([d.to_dict() for d in Department.query.all()])


@admin_bp.route('/departments', methods=['POST'])
@admin_required
def create_department():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Department name required'}), 400
    if Department.query.filter_by(name=name).first():
        return jsonify({'error': 'Department already exists'}), 409
    try:
        dept = Department(name=name, description=data.get('description', ''))
        db.session.add(dept)
        db.session.commit()
        return jsonify(dept.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
