from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from backend.models import db, User, Patient, Doctor
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if user.is_blacklisted:
        return jsonify({'error': 'Your account has been suspended. Contact admin.'}), 403

    token = create_access_token(
        identity=str(user.id),
        additional_claims={'role': user.role}
    )

    profile = None
    if user.role == 'doctor' and user.doctor_profile:
        profile = user.doctor_profile.to_dict()
    elif user.role == 'patient' and user.patient_profile:
        profile = user.patient_profile.to_dict()

    return jsonify({'access_token': token, 'user': user.to_dict(), 'profile': profile})


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username  = data.get('username', '').strip()
    email     = data.get('email', '').strip()
    password  = data.get('password', '')
    full_name = data.get('full_name', '').strip()

    if not all([username, email, password, full_name]):
        return jsonify({'error': 'username, email, password and full_name are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    try:
        user = User(username=username, email=email, role='patient')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()   

       
        dob = None
        dob_str = data.get('date_of_birth', '')
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass  

        patient = Patient(
            user_id=user.id,
            full_name=full_name,
            phone=data.get('phone', ''),
            gender=data.get('gender', ''),
            date_of_birth=dob,
            address=data.get('address', ''),
        )
        db.session.add(patient)
        db.session.commit()

        token = create_access_token(
            identity=str(user.id),
            additional_claims={'role': 'patient'}
        )
        return jsonify({
            'message': 'Registration successful',
            'access_token': token,
            'user': user.to_dict(),
            'profile': patient.to_dict(),
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    profile = None
    if user.role == 'doctor' and user.doctor_profile:
        profile = user.doctor_profile.to_dict()
    elif user.role == 'patient' and user.patient_profile:
        profile = user.patient_profile.to_dict()

    return jsonify({'user': user.to_dict(), 'profile': profile})
