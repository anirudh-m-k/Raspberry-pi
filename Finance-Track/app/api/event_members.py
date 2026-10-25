from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.event import Event
from app.models.event_member import EventMember
from app.models.event_expense import EventExpense
from app.models.event_expense_split import EventExpenseSplit
from app.models.event_participation import EventParticipation
from app.utils.decorators import token_required

event_members_api = Blueprint('event_members_api', __name__)


def check_event_ownership(event_id, current_user):
    event = Event.query.get_or_404(event_id)
    is_owner = event.user_id == current_user.id
    is_participant = EventParticipation.query.filter_by(
        event_id=event.id, user_id=current_user.id
    ).first() is not None
    if not (is_owner or is_participant):
        return None, jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return event, None, None


@event_members_api.route('', methods=['GET'])
@token_required
def list_members(current_user, event_id):
    """List all members of an event."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code
    members = EventMember.query.filter_by(event_id=event_id).order_by(EventMember.created_at).all()
    return jsonify({'success': True, 'data': [m.to_dict() for m in members]}), 200


@event_members_api.route('', methods=['POST'])
@token_required
def add_member(current_user, event_id):
    """Add a member to an event."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Member name is required'}}), 400

    member = EventMember(
        event_id=event_id,
        name=name,
        nickname=data.get('nickname'),
        color=data.get('color', '#6366f1'),
        avatar=data.get('avatar'),
        is_organizer=data.get('is_organizer', False),
    )
    db.session.add(member)
    db.session.commit()
    return jsonify({'success': True, 'data': member.to_dict(), 'message': 'Member added successfully'}), 201


@event_members_api.route('/<int:member_id>', methods=['PUT'])
@token_required
def update_member(current_user, event_id, member_id):
    """Update a member."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    member = EventMember.query.filter_by(id=member_id, event_id=event_id).first_or_404()
    data = request.get_json() or {}

    if 'name' in data and data['name'].strip():
        member.name = data['name'].strip()
    if 'nickname' in data:
        member.nickname = data['nickname']
    if 'color' in data:
        member.color = data['color']
    if 'avatar' in data:
        member.avatar = data['avatar']
    if 'is_organizer' in data:
        member.is_organizer = data['is_organizer']

    db.session.commit()
    return jsonify({'success': True, 'data': member.to_dict(), 'message': 'Member updated successfully'}), 200


@event_members_api.route('/<int:member_id>', methods=['DELETE'])
@token_required
def remove_member(current_user, event_id, member_id):
    """Remove a member. Blocked if has existing expenses."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    member = EventMember.query.filter_by(id=member_id, event_id=event_id).first_or_404()

    # Block if member has paid expenses
    paid_count = EventExpense.query.filter_by(paid_by_member_id=member_id).count()
    split_count = EventExpenseSplit.query.filter_by(member_id=member_id).count()
    if paid_count > 0 or split_count > 0:
        return jsonify({
            'success': False,
            'error': {'code': 'MEMBER_HAS_EXPENSES', 'message': 'Cannot remove member with existing expenses'}
        }), 400

    db.session.delete(member)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Member removed successfully'}), 200
