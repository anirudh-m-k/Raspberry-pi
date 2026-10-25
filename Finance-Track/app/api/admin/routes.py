from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import func
from app.extensions import db, limiter
from app.models.user import User
from app.models.expense import Expense
from app.models.income import Income
from app.models.account import Account
from app.models.goal import Goal
from app.models.budget import Budget
from app.models.audit_log import AuditLog
from app.utils.decorators import admin_required

admin_api = Blueprint('admin_api', __name__)


@admin_api.route('/dashboard', methods=['GET'])
@admin_required
def dashboard(current_user):
    """
    Get admin dashboard summary
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: Dashboard summary (user counts only)
      403:
        description: Admin access required
    """
    total_users = User.query.count()
    today = datetime.utcnow().date()
    active_today = User.query.filter(User.last_login >= today).count()
    week_ago = today - timedelta(days=7)
    new_this_week = User.query.filter(User.created_at >= week_ago).count()

    return jsonify({
        'success': True,
        'data': {
            'total_users': total_users,
            'active_users_today': active_today,
            'new_users_this_week': new_this_week,
        }
    }), 200


@admin_api.route('/users', methods=['GET'])
@admin_required
def list_users(current_user):
    """
    List all users with pagination and search
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
      - name: search
        in: query
        type: string
        description: Search by name or email
      - name: status
        in: query
        type: string
        enum: [active, inactive]
    responses:
      200:
        description: List of users
      403:
        description: Admin access required
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)  # SECURITY: cap at 100
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()

    query = User.query

    if search:
        query = query.filter(
            (User.name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )

    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    query = query.order_by(User.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    users = []
    for u in pagination.items:
        users.append({
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'is_active': u.is_active,
            'is_verified': u.is_verified,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'created_at': u.created_at.isoformat(),
        })

    return jsonify({
        'success': True,
        'data': users,
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@admin_api.route('/users/<user_id>', methods=['GET'])
@admin_required
def get_user(current_user, user_id):
    """
    Get user details (profile + counts only, no financial data)
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: string
    responses:
      200:
        description: User details
      404:
        description: User not found
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'User not found'}}), 404

    account_count = Account.query.filter_by(user_id=user.id).count()
    goal_count = Goal.query.filter_by(user_id=user.id).count()
    recent_logs = AuditLog.query.filter_by(user_id=user.id).order_by(AuditLog.created_at.desc()).limit(10).all()

    return jsonify({
        'success': True,
        'data': {
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'is_verified': user.is_verified,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'last_login_ip': user.last_login_ip,
                'created_at': user.created_at.isoformat(),
            },
            'counts': {
                'accounts': account_count,
                'goals': goal_count,
            },
            'recent_activity': [{
                'id': log.id,
                'action': log.action,
                'details': log.details,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat(),
            } for log in recent_logs],
        }
    }), 200


@admin_api.route('/users/<user_id>/status', methods=['PUT'])
@admin_required
def update_user_status(current_user, user_id):
    """
    Activate or deactivate a user
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - is_active
          properties:
            is_active:
              type: boolean
    responses:
      200:
        description: User status updated
      400:
        description: Invalid input
      403:
        description: Cannot deactivate yourself
      404:
        description: User not found
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'User not found'}}), 404

    # SECURITY: Admin cannot deactivate themselves
    if user.id == current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Cannot change your own status'}}), 403

    data = request.get_json()
    if 'is_active' not in data:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'is_active field is required'}}), 400

    if not isinstance(data['is_active'], bool):
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'is_active must be a boolean'}}), 400

    user.is_active = data['is_active']
    db.session.commit()

    action = 'activated' if user.is_active else 'deactivated'
    log = AuditLog(
        user_id=current_user.id,
        action=f'user_{action}',
        entity_type='user',
        entity_id=user.id,
        details=f'Admin {action} user {user.email}',
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'is_active': user.is_active,
        },
        'message': f'User {action} successfully'
    }), 200


@admin_api.route('/users/<user_id>/role', methods=['PUT'])
@admin_required
def update_user_role(current_user, user_id):
    """
    Change a user's role (user/admin)
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - role
          properties:
            role:
              type: string
              enum: [user, admin]
    responses:
      200:
        description: Role updated
      400:
        description: Invalid role
      403:
        description: Cannot change own role
      404:
        description: User not found
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'User not found'}}), 404

    # SECURITY: Admin cannot change their own role
    if user.id == current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Cannot change your own role'}}), 403

    data = request.get_json()
    new_role = data.get('role', '').strip().lower()

    if new_role not in ('user', 'admin'):
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Role must be "user" or "admin"'}}), 400

    if user.role == new_role:
        return jsonify({'success': False, 'error': {'code': 'NO_CHANGE', 'message': f'User already has role: {new_role}'}}), 400

    old_role = user.role
    user.role = new_role
    db.session.commit()

    # Log the role change
    log = AuditLog(
        user_id=current_user.id,
        action='role_changed',
        entity_type='user',
        entity_id=user.id,
        details=f'Admin changed {user.email} role from {old_role} to {new_role}',
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
        },
        'message': f'User role changed to {new_role}'
    }), 200


@admin_api.route('/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(current_user, user_id):
    """
    Delete a user (requires admin password)
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - password
          properties:
            password:
              type: string
              description: Admin's password for confirmation
    responses:
      200:
        description: User deleted
      400:
        description: Password required or incorrect
      403:
        description: Cannot delete yourself
      404:
        description: User not found
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'User not found'}}), 404

    # SECURITY: Admin cannot delete themselves
    if user.id == current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Cannot delete your own account'}}), 403

    # SECURITY: Verify admin password
    data = request.get_json()
    if not data or not data.get('password'):
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Password is required'}}), 400

    if not current_user.check_password(data['password']):
        return jsonify({'success': False, 'error': {'code': 'INVALID_PASSWORD', 'message': 'Incorrect password'}}), 400

    # Log before deletion
    log = AuditLog(
        user_id=current_user.id,
        action='user_deleted',
        entity_type='user',
        entity_id=user.id,
        details=f'Admin deleted user {user.email}',
        ip_address=request.remote_addr,
    )
    db.session.add(log)

    # Delete user's data (cascade not configured on User model, so delete manually)
    from app.models.expense import Expense
    from app.models.income import Income
    from app.models.account import Account
    from app.models.budget import Budget
    from app.models.goal import Goal, GoalContribution
    from app.models.savings_pot import SavingsPot, SavingsPotTransaction
    from app.models.recurring import RecurringTransaction
    from app.models.notification import Notification
    from app.models.setting import Setting
    from app.models.category import Category
    from app.models.reports_cache import ReportsCache

    # Delete in order to respect foreign keys
    GoalContribution.query.filter_by(user_id=user.id).delete()
    SavingsPotTransaction.query.filter_by(user_id=user.id).delete()
    Expense.query.filter_by(user_id=user.id).delete()
    Income.query.filter_by(user_id=user.id).delete()
    RecurringTransaction.query.filter_by(user_id=user.id).delete()
    Budget.query.filter_by(user_id=user.id).delete()
    Goal.query.filter_by(user_id=user.id).delete()
    SavingsPot.query.filter_by(user_id=user.id).delete()
    Account.query.filter_by(user_id=user.id).delete()
    Notification.query.filter_by(user_id=user.id).delete()
    Category.query.filter_by(user_id=user.id).delete()
    ReportsCache.query.filter_by(user_id=user.id).delete()
    Setting.query.filter_by(user_id=user.id).delete()
    AuditLog.query.filter_by(user_id=user.id).delete()

    user_name = user.name
    user_email = user.email
    db.session.delete(user)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'User {user_name} ({user_email}) and all their data has been deleted'
    }), 200


@admin_api.route('/audit-logs', methods=['GET'])
@admin_required
def list_audit_logs(current_user):
    """
    List audit logs with filters
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
      - name: user_id
        in: query
        type: string
      - name: action
        in: query
        type: string
    responses:
      200:
        description: List of audit logs
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    user_id = request.args.get('user_id', '').strip()
    action = request.args.get('action', '').strip()

    query = AuditLog.query

    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))

    query = query.order_by(AuditLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    logs = []
    for log in pagination.items:
        user = User.query.get(log.user_id)
        logs.append({
            'id': log.id,
            'user_id': log.user_id,
            'user_name': user.name if user else 'Unknown',
            'user_email': user.email if user else 'Unknown',
            'action': log.action,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'details': log.details,
            'ip_address': log.ip_address,
            'created_at': log.created_at.isoformat(),
        })

    return jsonify({
        'success': True,
        'data': logs,
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200
