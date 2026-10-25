from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from app.extensions import db, limiter
from app.models.user import User
from app.models.setting import Setting
from app.services.audit_service import log_audit
from app.services.email_service import generate_otp, send_password_reset_otp, send_welcome_email, send_password_changed_email
from app.utils.validators import validate_email, validate_password_strength
from app.utils.decorators import token_required, generate_token

auth_api = Blueprint('auth_api', __name__)

# In-memory OTP store for password reset: {email: {'otp': '123456', 'expires_at': datetime, 'attempts': 0}}
# In production, use Redis with TTL
password_reset_otps = {}


@auth_api.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """
    Register a new user
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - email
            - password
            - confirm_password
          properties:
            name:
              type: string
              example: John Doe
            email:
              type: string
              example: john@example.com
            password:
              type: string
              example: SecurePass123
            confirm_password:
              type: string
              example: SecurePass123
    responses:
      201:
        description: Registration successful
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                token:
                  type: string
                user:
                  type: object
            message:
              type: string
      400:
        description: Validation error
      409:
        description: Email already registered
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not name or not email or not password:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Name, email, and password are required'}}), 400

    if not validate_email(email):
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid email format'}}), 400

    if password != confirm_password:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Passwords do not match'}}), 400

    is_valid, msg = validate_password_strength(password)
    if not is_valid:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': msg}}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': {'code': 'DUPLICATE', 'message': 'Email already registered'}}), 409

    # First registered user becomes admin automatically
    is_first_user = User.query.count() == 0
    role = 'admin' if is_first_user else 'user'

    user = User(name=name, email=email, is_verified=True, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    settings = Setting(user_id=user.id)
    db.session.add(settings)
    db.session.commit()

    token = generate_token(user)

    # Send welcome email
    send_welcome_email(email, name)

    return jsonify({
        'success': True,
        'data': {'token': token, 'user': user.to_dict()},
        'message': 'Registration successful'
    }), 201


@auth_api.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """
    Login user
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              example: john@example.com
            password:
              type: string
              example: SecurePass123
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                token:
                  type: string
                user:
                  type: object
            message:
              type: string
      401:
        description: Invalid credentials
    """
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Email and password are required'}}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Invalid email or password'}}), 401

    if not user.is_active:
        return jsonify({'success': False, 'error': {'code': 'ACCOUNT_DISABLED', 'message': 'Your account has been disabled'}}), 403

    user.last_login = datetime.utcnow()
    user.last_login_ip = request.remote_addr
    db.session.commit()

    token = generate_token(user)
    return jsonify({
        'success': True,
        'data': {'token': token, 'user': user.to_dict()},
        'message': 'Login successful'
    }), 200


@auth_api.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """
    Logout user
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Logout successful
    """
    # Add token to blacklist to prevent reuse
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    try:
        import jwt as pyjwt
        from flask import current_app
        payload = pyjwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        from app.extensions import token_blacklist
        token_blacklist.add(payload.get('jti'))
    except Exception:
        pass  # Token already invalid, logout still succeeds

    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200


@auth_api.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    """
    Request password reset - sends OTP to email
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
          properties:
            email:
              type: string
              example: john@example.com
    responses:
      200:
        description: OTP sent (if email exists)
    """
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Email is required'}}), 400

    # Always return success to prevent email enumeration
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            'success': True,
            'message': 'If the email exists, an OTP has been sent'
        }), 200

    # Generate and store OTP
    otp = generate_otp()
    password_reset_otps[email] = {
        'otp': otp,
        'expires_at': datetime.utcnow() + timedelta(minutes=10),
        'attempts': 0
    }

    # Send OTP email
    send_password_reset_otp(email, otp)

    return jsonify({
        'success': True,
        'message': 'If the email exists, an OTP has been sent'
    }), 200


@auth_api.route('/verify-reset-otp', methods=['POST'])
@limiter.limit("5 per minute")
def verify_reset_otp():
    """
    Verify password reset OTP
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - otp
          properties:
            email:
              type: string
            otp:
              type: string
    responses:
      200:
        description: OTP verified
      400:
        description: Invalid or expired OTP
    """
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()

    if not email or not otp:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Email and OTP are required'}}), 400

    otp_data = password_reset_otps.get(email)
    if not otp_data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_OTP', 'message': 'No OTP request found. Please request a new one.'}}), 400

    # Check expiration
    if datetime.utcnow() > otp_data['expires_at']:
        del password_reset_otps[email]
        return jsonify({'success': False, 'error': {'code': 'OTP_EXPIRED', 'message': 'OTP has expired. Please request a new one.'}}), 400

    # Check attempts
    if otp_data['attempts'] >= 5:
        del password_reset_otps[email]
        return jsonify({'success': False, 'error': {'code': 'TOO_MANY_ATTEMPTS', 'message': 'Too many failed attempts. Please request a new OTP.'}}), 429

    # Increment attempts
    otp_data['attempts'] += 1

    # Verify OTP
    if otp_data['otp'] != otp:
        return jsonify({'success': False, 'error': {'code': 'INVALID_OTP', 'message': 'Invalid OTP. Please try again.'}}), 400

    # OTP verified - mark email as verified for reset
    password_reset_otps[email]['verified'] = True

    return jsonify({
        'success': True,
        'message': 'OTP verified successfully'
    }), 200


@auth_api.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    """
    Reset password after OTP verification
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - otp
            - new_password
          properties:
            email:
              type: string
            otp:
              type: string
            new_password:
              type: string
    responses:
      200:
        description: Password reset successful
      400:
        description: Invalid OTP or validation error
    """
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not email or not otp or not new_password:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Email, OTP, and new password are required'}}), 400

    # Validate password strength
    is_valid, msg = validate_password_strength(new_password)
    if not is_valid:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': msg}}), 400

    # Check OTP data
    otp_data = password_reset_otps.get(email)
    if not otp_data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_OTP', 'message': 'No OTP request found. Please request a new one.'}}), 400

    # Check expiration
    if datetime.utcnow() > otp_data['expires_at']:
        del password_reset_otps[email]
        return jsonify({'success': False, 'error': {'code': 'OTP_EXPIRED', 'message': 'OTP has expired. Please request a new one.'}}), 400

    # Verify OTP
    if otp_data['otp'] != otp:
        return jsonify({'success': False, 'error': {'code': 'INVALID_OTP', 'message': 'Invalid OTP. Please try again.'}}), 400

    # Check if OTP was verified
    if not otp_data.get('verified'):
        return jsonify({'success': False, 'error': {'code': 'OTP_NOT_VERIFIED', 'message': 'Please verify OTP first.'}}), 400

    # Find user and update password
    user = User.query.filter_by(email=email).first()
    if not user:
        del password_reset_otps[email]
        return jsonify({'success': False, 'error': {'code': 'USER_NOT_FOUND', 'message': 'User not found.'}}), 404

    # Update password
    user.set_password(new_password)
    db.session.commit()

    # Clean up OTP
    del password_reset_otps[email]

    # Log audit
    log_audit(user.id, 'password_reset')

    # Send notification email
    send_password_changed_email(user.email, user.name)

    return jsonify({
        'success': True,
        'message': 'Password reset successful. You can now login with your new password.'
    }), 200
