import os
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.setting import Setting
from app.models.category import Category
from app.models.user import User
from app.utils.decorators import token_required, admin_required
from app.utils.validators import validate_password_strength
from app.services.audit_service import log_audit
from app.services.email_service import send_password_changed_email

settings_api = Blueprint('settings_api', __name__)


@settings_api.route('', methods=['GET'])
@token_required
def get_settings(current_user):
    """
    Get user settings
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    responses:
      200:
        description: User settings
    """
    settings = Setting.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Setting(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    return jsonify({'success': True, 'data': settings.to_dict()}), 200


@settings_api.route('', methods=['PUT'])
@token_required
def update_settings(current_user):
    """
    Update user settings and profile
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
            currency:
              type: string
            timezone:
              type: string
            theme:
              type: string
              enum: [light, dark]
            date_format:
              type: string
            month_start_day:
              type: integer
            session_timeout_minutes:
              type: integer
            notification_email:
              type: boolean
            notification_browser:
              type: boolean
            backup_frequency:
              type: string
    responses:
      200:
        description: Settings updated
    """
    settings = Setting.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Setting(user_id=current_user.id)
        db.session.add(settings)

    data = request.get_json()

    if 'name' in data:
        current_user.name = data['name']

    for field in ['currency', 'timezone', 'theme', 'date_format', 'month_start_day',
                  'session_timeout_minutes', 'notification_email', 'notification_browser', 'backup_frequency']:
        if field in data:
            setattr(settings, field, data[field])

    db.session.commit()
    return jsonify({'success': True, 'data': settings.to_dict(), 'message': 'Settings updated'}), 200


@settings_api.route('/categories', methods=['GET'])
@token_required
def list_categories(current_user):
    """
    List categories (default + custom)
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - name: type
        in: query
        type: string
        enum: [expense, income]
    responses:
      200:
        description: List of categories
    """
    type_filter = request.args.get('type')
    query = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.is_default == True)
    )
    if type_filter:
        query = query.filter_by(type=type_filter)
    categories = query.all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in categories]}), 200


@settings_api.route('/categories', methods=['POST'])
@token_required
def add_category(current_user):
    """
    Add a custom category
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - type
          properties:
            name:
              type: string
            type:
              type: string
              enum: [expense, income]
            icon:
              type: string
            color:
              type: string
            parent_id:
              type: integer
    responses:
      201:
        description: Category created
      409:
        description: Category already exists
    """
    data = request.get_json()
    name = data.get('name', '').strip()
    cat_type = data.get('type', '').strip()
    if not name or not cat_type:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Name and type are required'}}), 400

    existing = Category.query.filter_by(
        user_id=current_user.id, name=name, type=cat_type, parent_id=data.get('parent_id')
    ).first()
    if existing:
        return jsonify({'success': False, 'error': {'code': 'DUPLICATE', 'message': 'Category already exists'}}), 409

    category = Category(
        user_id=current_user.id,
        name=name,
        type=cat_type,
        icon=data.get('icon'),
        color=data.get('color'),
        parent_id=data.get('parent_id'),
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({'success': True, 'data': category.to_dict(), 'message': 'Category created'}), 201


@settings_api.route('/categories/<int:cat_id>', methods=['DELETE'])
@token_required
def delete_category(current_user, cat_id):
    """
    Delete a custom category
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - name: cat_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Category deleted
      403:
        description: Cannot delete default categories
    """
    category = Category.query.get_or_404(cat_id)
    if category.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    if category.is_default:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Cannot delete default categories'}}), 403
    db.session.delete(category)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Category deleted'}), 200


@settings_api.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """
    Change user password
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - current_password
            - new_password
          properties:
            current_password:
              type: string
            new_password:
              type: string
    responses:
      200:
        description: Password changed
      400:
        description: Invalid current password
    """
    data = request.get_json()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_user.check_password(current_password):
        return jsonify({'success': False, 'error': {'code': 'INVALID_PASSWORD', 'message': 'Current password is incorrect'}}), 400

    is_valid, msg = validate_password_strength(new_password)
    if not is_valid:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': msg}}), 400

    current_user.set_password(new_password)
    db.session.commit()
    log_audit(current_user.id, 'password_change')
    send_password_changed_email(current_user.email, current_user.name)
    return jsonify({'success': True, 'message': 'Password changed successfully'}), 200


@settings_api.route('/export-data', methods=['POST'])
@token_required
def export_data(current_user):
    """
    Export all user data as JSON
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    responses:
      200:
        description: JSON export of all user data
    """
    from app.models.expense import Expense
    from app.models.income import Income
    from app.models.goal import Goal
    from app.models.savings_pot import SavingsPot
    from app.models.account import Account
    from app.models.budget import Budget

    data = {
        'user': current_user.to_dict(),
        'expenses': [e.to_dict() for e in Expense.query.filter_by(user_id=current_user.id).all()],
        'income': [i.to_dict() for i in Income.query.filter_by(user_id=current_user.id).all()],
        'accounts': [a.to_dict() for a in Account.query.filter_by(user_id=current_user.id).all()],
        'budgets': [b.to_dict() for b in Budget.query.filter_by(user_id=current_user.id).all()],
        'goals': [g.to_dict() for g in Goal.query.filter_by(user_id=current_user.id).all()],
        'savings_pots': [p.to_dict() for p in SavingsPot.query.filter_by(user_id=current_user.id).all()],
    }
    log_audit(current_user.id, 'data_export')
    return jsonify({'success': True, 'data': data}), 200


@settings_api.route('/backup', methods=['POST'])
@admin_required
def create_backup(current_user):
    """
    Create a database backup
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    responses:
      200:
        description: Backup file download
      500:
        description: Backup failed
    """
    from app.services.backup_service import create_backup as do_backup
    from flask import send_file
    import os

    backup_path = do_backup()
    if backup_path and os.path.exists(backup_path):
        log_audit(current_user.id, 'backup_created')
        return send_file(backup_path, as_attachment=True, download_name=os.path.basename(backup_path))

    return jsonify({'success': False, 'error': {'code': 'BACKUP_FAILED', 'message': 'Failed to create backup'}}), 500


@settings_api.route('/restore-backup', methods=['POST'])
@admin_required
def restore_backup(current_user):
    """
    Restore database from uploaded backup file
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - name: backup_file
        in: formData
        type: file
        required: true
        description: SQLite database backup file (.db)
      - name: password
        in: formData
        type: string
        required: true
        description: User password for confirmation
    responses:
      200:
        description: Backup restored successfully
      400:
        description: Invalid file or password
    """
    from flask import request
    import tempfile

    password = request.form.get('password', '')
    if not current_user.check_password(password):
        return jsonify({'success': False, 'error': {'code': 'INVALID_PASSWORD', 'message': 'Incorrect password'}}), 400

    if 'backup_file' not in request.files:
        return jsonify({'success': False, 'error': {'code': 'NO_FILE', 'message': 'No file uploaded'}}), 400

    file = request.files['backup_file']
    if not file.filename or not file.filename.endswith('.db'):
        return jsonify({'success': False, 'error': {'code': 'INVALID_FILE', 'message': 'File must be a .db SQLite database'}}), 400

    # Save uploaded file temporarily
    temp_path = tempfile.mktemp(suffix='.db')
    try:
        file.save(temp_path)

        # Validate it's a valid SQLite database
        import sqlite3
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            required_tables = ['users', 'expenses', 'income', 'accounts']
            missing = [t for t in required_tables if t not in tables]
            if missing:
                return jsonify({'success': False, 'error': {'code': 'INVALID_DB', 'message': f'Invalid backup: missing tables: {", ".join(missing)}'}}), 400
        except Exception:
            return jsonify({'success': False, 'error': {'code': 'INVALID_DB', 'message': 'File is not a valid SQLite database'}}), 400

        # Create a backup of current DB before restoring
        from app.services.backup_service import create_backup
        create_backup()

        # Restore the backup
        from app.services.backup_service import restore_backup as do_restore
        success = do_restore(temp_path)

        if success:
            log_audit(current_user.id, 'backup_restored', details=f'Restored from: {file.filename}')
            return jsonify({
                'success': True,
                'message': 'Backup restored successfully. Please log out and log back in to see the changes.'
            }), 200
        else:
            return jsonify({'success': False, 'error': {'code': 'RESTORE_FAILED', 'message': 'Failed to restore backup'}}), 500

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


@settings_api.route('/request-delete-otp', methods=['POST'])
@token_required
def request_delete_otp(current_user):
    """
    Request OTP for account deletion
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    responses:
      200:
        description: OTP sent
    """
    from app.services.email_service import generate_otp, send_account_deletion_otp
    from app.api.auth import password_reset_otps
    from datetime import datetime, timedelta

    otp = generate_otp()
    password_reset_otps[current_user.email] = {
        'otp': otp,
        'expires_at': datetime.utcnow() + timedelta(minutes=10),
        'attempts': 0,
        'purpose': 'account_delete'
    }

    send_account_deletion_otp(current_user.email, otp)

    return jsonify({
        'success': True,
        'message': 'OTP sent to your email'
    }), 200


@settings_api.route('/delete-account', methods=['POST'])
@token_required
def delete_account(current_user):
    """
    Delete user's own account (requires password + OTP)
    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - password
            - otp
          properties:
            password:
              type: string
            otp:
              type: string
    responses:
      200:
        description: Account deleted
      400:
        description: Invalid password or OTP
    """
    from app.api.auth import password_reset_otps

    data = request.get_json()
    password = data.get('password', '')
    otp = data.get('otp', '').strip()

    if not password or not otp:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Password and OTP are required'}}), 400

    # Verify password
    if not current_user.check_password(password):
        return jsonify({'success': False, 'error': {'code': 'INVALID_PASSWORD', 'message': 'Incorrect password'}}), 400

    # Verify OTP
    otp_data = password_reset_otps.get(current_user.email)
    if not otp_data or otp_data.get('purpose') != 'account_delete':
        return jsonify({'success': False, 'error': {'code': 'INVALID_OTP', 'message': 'No OTP request found. Please request a new one.'}}), 400

    if datetime.utcnow() > otp_data['expires_at']:
        del password_reset_otps[current_user.email]
        return jsonify({'success': False, 'error': {'code': 'OTP_EXPIRED', 'message': 'OTP has expired. Please request a new one.'}}), 400

    if otp_data['otp'] != otp:
        otp_data['attempts'] += 1
        if otp_data['attempts'] >= 5:
            del password_reset_otps[current_user.email]
        return jsonify({'success': False, 'error': {'code': 'INVALID_OTP', 'message': 'Invalid OTP.'}}), 400

    # All checks passed - delete all user data
    from app.models.expense import Expense
    from app.models.income import Income
    from app.models.account import Account
    from app.models.budget import Budget
    from app.models.goal import Goal, GoalContribution
    from app.models.savings_pot import SavingsPot, SavingsPotTransaction
    from app.models.recurring import RecurringTransaction
    from app.models.notification import Notification
    from app.models.category import Category
    from app.models.reports_cache import ReportsCache
    from app.models.audit_log import AuditLog as AuditLogModel

    user_email = current_user.email

    GoalContribution.query.filter_by(user_id=current_user.id).delete()
    SavingsPotTransaction.query.filter_by(user_id=current_user.id).delete()
    Expense.query.filter_by(user_id=current_user.id).delete()
    Income.query.filter_by(user_id=current_user.id).delete()
    RecurringTransaction.query.filter_by(user_id=current_user.id).delete()
    Budget.query.filter_by(user_id=current_user.id).delete()
    Goal.query.filter_by(user_id=current_user.id).delete()
    SavingsPot.query.filter_by(user_id=current_user.id).delete()
    Account.query.filter_by(user_id=current_user.id).delete()
    Notification.query.filter_by(user_id=current_user.id).delete()
    Category.query.filter_by(user_id=current_user.id).delete()
    ReportsCache.query.filter_by(user_id=current_user.id).delete()
    Setting.query.filter_by(user_id=current_user.id).delete()
    AuditLogModel.query.filter_by(user_id=current_user.id).delete()

    # Clean up OTP
    if current_user.email in password_reset_otps:
        del password_reset_otps[current_user.email]

    db.session.delete(current_user)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Your account and all associated data have been permanently deleted'
    }), 200
