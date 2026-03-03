from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  
    is_active = db.Column(db.Boolean, default=True)
    is_blacklisted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor_profile = db.relationship('Doctor', backref='user', uselist=False, cascade='all, delete-orphan')
    patient_profile = db.relationship('Patient', backref='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'is_blacklisted': self.is_blacklisted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    
    doctors = db.relationship('Doctor', backref='department', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'doctors_count': len(self.doctors),
        }


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    full_name = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(150))
    qualification = db.Column(db.String(200))
    experience_years = db.Column(db.Integer, default=0)
    bio = db.Column(db.Text)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    availabilities = db.relationship('DoctorAvailability', backref='doctor', lazy='select',
                                     cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='doctor', lazy='select')

    def to_dict(self):
        dept = None
        if self.department_id:
            dept = db.session.get(Department, self.department_id)
        return {
            'id': self.id,
            'user_id': self.user_id,
            'full_name': self.full_name,
            'specialization': self.specialization or '',
            'qualification': self.qualification or '',
            'experience_years': self.experience_years or 0,
            'bio': self.bio or '',
            'phone': self.phone or '',
            'department_id': self.department_id,
            'department_name': dept.name if dept else None,
            'username': self.user.username if self.user else None,
            'email': self.user.email if self.user else None,
            'is_blacklisted': self.user.is_blacklisted if self.user else False,
        }


class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availabilities'
    __table_args__ = (
        db.UniqueConstraint('doctor_id', 'date', name='uq_doctor_date'),
    )
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    morning_start = db.Column(db.String(10), default='08:00')
    morning_end = db.Column(db.String(10), default='12:00')
    evening_start = db.Column(db.String(10), default='16:00')
    evening_end = db.Column(db.String(10), default='21:00')
    morning_available = db.Column(db.Boolean, default=True)
    evening_available = db.Column(db.Boolean, default=True)
    is_available = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'date': self.date.isoformat(),
            'morning_start': self.morning_start,
            'morning_end': self.morning_end,
            'evening_start': self.evening_start,
            'evening_end': self.evening_end,
            'morning_available': self.morning_available,
            'evening_available': self.evening_available,
            'is_available': self.is_available,
        }


class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    blood_group = db.Column(db.String(5))
    emergency_contact = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='patient', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender or '',
            'phone': self.phone or '',
            'address': self.address or '',
            'blood_group': self.blood_group or '',
            'emergency_contact': self.emergency_contact or '',
            'username': self.user.username if self.user else None,
            'email': self.user.email if self.user else None,
            'is_blacklisted': self.user.is_blacklisted if self.user else False,
        }


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)  
    status = db.Column(db.String(20), default='Booked')   
    visit_type = db.Column(db.String(50), default='In-person')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    treatment = db.relationship('Treatment', backref='appointment', uselist=False,
                                cascade='all, delete-orphan')

    def to_dict(self):
        
        try:
            patient_name = self.patient.full_name if self.patient else None
        except Exception:
            patient_name = None
        try:
            doctor_name = self.doctor.full_name if self.doctor else None
            dept_name = self.doctor.department.name if (self.doctor and self.doctor.department) else None
        except Exception:
            doctor_name = None
            dept_name = None
        try:
            treatment_dict = self.treatment.to_dict() if self.treatment else None
        except Exception:
            treatment_dict = None

        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': patient_name,
            'doctor_id': self.doctor_id,
            'doctor_name': doctor_name,
            'department': dept_name,
            'date': self.date.isoformat() if self.date else None,
            'time_slot': self.time_slot,
            'status': self.status,
            'visit_type': self.visit_type,
            'notes': self.notes or '',
            'treatment': treatment_dict,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Treatment(db.Model):
    __tablename__ = 'treatments'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    medicines = db.Column(db.Text)
    tests_done = db.Column(db.String(200))
    next_visit = db.Column(db.Date, nullable=True)
    doctor_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_id': self.appointment_id,
            'diagnosis': self.diagnosis or '',
            'prescription': self.prescription or '',
            'medicines': self.medicines or '',
            'tests_done': self.tests_done or '',
            'next_visit': self.next_visit.isoformat() if self.next_visit else None,
            'doctor_notes': self.doctor_notes or '',
        }
