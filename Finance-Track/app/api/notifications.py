from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.notification import Notification
from app.utils.decorators import token_required

notifications_api = Blueprint('notifications_api', __name__)


@notifications_api.route('', methods=['GET'])
@token_required
def list_notifications(current_user):
    """
    List notifications with pagination
    ---
    tags:
      - Notifications
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
      - name: unread_only
        in: query
        type: boolean
        default: false
    responses:
      200:
        description: List of notifications with unread count
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'

    query = Notification.query.filter_by(user_id=current_user.id)
    if unread_only:
        query = query.filter_by(is_read=False)

    query = query.order_by(Notification.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

    return jsonify({
        'success': True,
        'data': {
            'notifications': [n.to_dict() for n in pagination.items],
            'unread_count': unread_count,
        },
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@notifications_api.route('/<int:notif_id>/read', methods=['PUT'])
@token_required
def mark_read(current_user, notif_id):
    """
    Mark notification as read
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    parameters:
      - name: notif_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Notification marked as read
    """
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True, 'message': 'Notification marked as read'}), 200


@notifications_api.route('/read-all', methods=['PUT'])
@token_required
def mark_all_read(current_user):
    """
    Mark all notifications as read
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    responses:
      200:
        description: All notifications marked as read
    """
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True, 'message': 'All notifications marked as read'}), 200


@notifications_api.route('/<int:notif_id>', methods=['DELETE'])
@token_required
def delete_notification(current_user, notif_id):
    """
    Delete a notification
    ---
    tags:
      - Notifications
    security:
      - Bearer: []
    parameters:
      - name: notif_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Notification deleted
    """
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Notification deleted'}), 200
