from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from app.extensions import db
from app.models.event import Event
from app.models.event_member import EventMember
from app.models.event_participation import EventParticipation
from app.utils.decorators import token_required
from app.services.event_service import EventService

events_api = Blueprint('events_api', __name__)


def can_access_event(event, user_id):
    """Return True if user is the event owner OR a joined participant."""
    if event.user_id == user_id:
        return True
    return EventParticipation.query.filter_by(
        event_id=event.id, user_id=user_id
    ).first() is not None


@events_api.route('', methods=['GET'])
@token_required
def list_events(current_user):
    """List events: owned by user OR joined via invite code."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')

    # Sub-query: event IDs the user joined as a participant
    joined_event_ids = db.session.query(EventParticipation.event_id).filter_by(
        user_id=current_user.id
    ).subquery()

    query = Event.query.filter(
        or_(
            Event.user_id == current_user.id,
            Event.id.in_(joined_event_ids)
        )
    )
    if status:
        query = query.filter(Event.status == status)
    query = query.order_by(Event.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    events = []
    for e in pagination.items:
        EventService.update_status_on_fetch(e)
        events.append(e.to_dict())

    return jsonify({
        'success': True,
        'data': events,
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@events_api.route('', methods=['POST'])
@token_required
def create_event(current_user):
    """Create a new event with optional members, categories, and join code."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Event name is required'}}), 400

    generate_code = data.get('generate_join_code', False)
    try:
        event, join_code_obj = EventService.create_event_with_defaults(current_user.id, data, generate_join_code=generate_code)
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': {'code': 'INTERNAL_ERROR', 'message': str(e)}}), 500

    event_dict = event.to_dict()
    if join_code_obj:
        event_dict['join_code'] = join_code_obj.code

    return jsonify({
        'success': True,
        'data': event_dict,
        'message': 'Event created successfully'
    }), 201


@events_api.route('/<int:event_id>', methods=['GET'])
@token_required
def get_event(current_user, event_id):
    """Get event details."""
    event = Event.query.get_or_404(event_id)
    if not can_access_event(event, current_user.id):
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    EventService.update_status_on_fetch(event)
    return jsonify({'success': True, 'data': event.to_dict()}), 200


@events_api.route('/<int:event_id>', methods=['PUT'])
@token_required
def update_event(current_user, event_id):
    """Update an event (partial update)."""
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json() or {}
    if 'name' in data and data['name'].strip():
        event.name = data['name'].strip()
    if 'description' in data:
        event.description = data['description']
    if 'start_date' in data:
        event.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data['start_date'] else None
    if 'end_date' in data:
        event.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data['end_date'] else None
    if 'currency' in data:
        event.currency = data['currency']
    if 'budget' in data:
        event.budget = Decimal(str(data['budget'])) if data['budget'] else None
    if 'image_url' in data:
        event.image_url = data['image_url']
    if 'status' in data:
        from app.utils.constants import EVENT_STATUSES
        if data['status'] in EVENT_STATUSES:
            event.status = data['status']

    db.session.commit()
    return jsonify({
        'success': True,
        'data': event.to_dict(),
        'message': 'Event updated successfully'
    }), 200


@events_api.route('/<int:event_id>', methods=['DELETE'])
@token_required
def delete_event(current_user, event_id):
    """Delete an event and cascade to all related tables."""
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    db.session.delete(event)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Event deleted successfully'}), 200


@events_api.route('/join-by-code', methods=['POST'])
@token_required
def join_event_by_code(current_user):
    """Join an existing event using a join code."""
    data = request.get_json() or {}
    code = data.get('code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Join code is required'}}), 400

    event, error = EventService.join_event_by_code(code, current_user.id)
    if error and not event:
        return jsonify({'success': False, 'error': {'code': 'INVALID_CODE', 'message': error}}), 400

    return jsonify({
        'success': True,
        'data': event.to_dict() if event else None,
        'message': error or 'Joined event successfully'
    }), 200


@events_api.route('/<int:event_id>/join-codes', methods=['GET'])
@token_required
def list_join_codes(current_user, event_id):
    """List join codes for an event."""
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    from app.models.event_join_code import EventJoinCode
    codes = EventJoinCode.query.filter_by(
        event_id=event_id,
        created_by_user_id=current_user.id
    ).order_by(EventJoinCode.created_at.desc()).all()

    return jsonify({'success': True, 'data': [c.to_dict() for c in codes]}), 200


@events_api.route('/<int:event_id>/join-codes', methods=['POST'])
@token_required
def create_join_code(current_user, event_id):
    """Generate a new join code for an event."""
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json() or {}
    expires_at = None
    if data.get('expires_at'):
        try:
            expires_at = datetime.strptime(data['expires_at'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            expires_at = None
    max_uses = data.get('max_uses', 1)

    join_code = EventService.generate_event_join_code(
        event_id=event_id,
        created_by_user_id=current_user.id,
        expires_at=expires_at,
        max_uses=max_uses,
    )
    return jsonify({
        'success': True,
        'data': join_code.to_dict(),
        'message': f'Join code {join_code.code} generated'
    }), 201


@events_api.route('/<int:event_id>/join-codes/<int:code_id>', methods=['GET'])
@token_required
def get_join_code(current_user, event_id, code_id):
    """Get join code details."""
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    from app.models.event_join_code import EventJoinCode
    join_code = EventJoinCode.query.filter_by(id=code_id, event_id=event_id).first_or_404()
    return jsonify({'success': True, 'data': join_code.to_dict()}), 200


@events_api.route('/<int:event_id>/join-codes/<int:code_id>', methods=['DELETE'])
@token_required
def revoke_join_code(current_user, event_id, code_id):
    """Revoke a join code."""
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    from app.models.event_join_code import EventJoinCode
    join_code = EventJoinCode.query.filter_by(id=code_id, event_id=event_id).first_or_404()
    join_code.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'Join code revoked'}), 200


@events_api.route('/<int:event_id>/participation', methods=['GET'])
@token_required
def list_participation(current_user, event_id):
    """List all user participants for an event."""
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    from app.models.event_participation import EventParticipation
    participants = EventParticipation.query.filter_by(event_id=event_id).all()
    return jsonify({'success': True, 'data': [p.to_dict() for p in participants]}), 200
