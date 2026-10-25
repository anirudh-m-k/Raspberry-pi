from functools import wraps
from flask import jsonify
import jwt
import uuid
from datetime import datetime, timedelta
from flask import current_app, request
from app.models.user import User


def token_required(f):
    """Decorator to require JWT token for API endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNAUTHORIZED',
                    'message': 'Authentication token is missing'
                }
            }), 401

        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )

            # Check if token has been revoked (logout)
            from app.extensions import token_blacklist
            jti = payload.get('jti')
            if jti and jti in token_blacklist:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'TOKEN_REVOKED',
                        'message': 'Token has been revoked'
                    }
                }), 401

            user = User.query.get(payload['sub'])
            if not user or not user.is_active:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'UNAUTHORIZED',
                        'message': 'Invalid or expired token'
                    }
                }), 401
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'TOKEN_EXPIRED',
                    'message': 'Token has expired'
                }
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_TOKEN',
                    'message': 'Invalid token'
                }
            }), 401

        return f(user, *args, **kwargs)
    return decorated


def generate_token(user):
    """Generate JWT token for a user with unique ID for revocation support."""
    from flask import current_app
    expiration_hours = current_app.config.get('JWT_EXPIRATION_HOURS', 24)
    payload = {
        'sub': user.id,
        'jti': str(uuid.uuid4()),  # Unique token ID for revocation
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=expiration_hours)
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')


def admin_required(f):
    """Decorator to require admin role for API endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # First check token
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNAUTHORIZED',
                    'message': 'Authentication token is missing'
                }
            }), 401

        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )

            # Check if token has been revoked (logout)
            from app.extensions import token_blacklist
            jti = payload.get('jti')
            if jti and jti in token_blacklist:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'TOKEN_REVOKED',
                        'message': 'Token has been revoked'
                    }
                }), 401

            user = User.query.get(payload['sub'])
            if not user or not user.is_active:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'UNAUTHORIZED',
                        'message': 'Invalid or expired token'
                    }
                }), 401

            # Check admin role
            if not user.is_admin:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'FORBIDDEN',
                        'message': 'Admin access required'
                    }
                }), 403

        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'TOKEN_EXPIRED',
                    'message': 'Token has expired'
                }
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_TOKEN',
                    'message': 'Invalid token'
                }
            }), 401

        return f(user, *args, **kwargs)
    return decorated
