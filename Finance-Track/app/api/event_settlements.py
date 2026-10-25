from datetime import datetime
from flask import Blueprint, jsonify
from app.extensions import db
from app.models.event import Event
from app.models.event_settlement import EventSettlement
from app.models.event_participation import EventParticipation
from app.utils.decorators import token_required
from app.services.settlement_service import SettlementService

event_settlements_api = Blueprint('event_settlements_api', __name__)


def check_event_ownership(event_id, current_user):
    event = Event.query.get_or_404(event_id)
    is_owner = event.user_id == current_user.id
    is_participant = EventParticipation.query.filter_by(
        event_id=event.id, user_id=current_user.id
    ).first() is not None
    if not (is_owner or is_participant):
        return None, jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return event, None, None


@event_settlements_api.route('', methods=['GET'])
@token_required
def list_settlements(current_user, event_id):
    """List settlements for an event."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code
    settlements = EventSettlement.query.filter_by(event_id=event_id) \
        .order_by(EventSettlement.is_completed, EventSettlement.created_at.desc()).all()
    return jsonify({'success': True, 'data': [s.to_dict() for s in settlements]}), 200


@event_settlements_api.route('/calculate', methods=['POST'])
@token_required
def calculate_settlements(current_user, event_id):
    """Recalculate settlements (delete pending, create new)."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    # Delete all non-completed settlements
    EventSettlement.query.filter_by(event_id=event_id, is_completed=False).delete()
    db.session.flush()

    # Calculate new settlements
    settlements_data = SettlementService.calculate_settlements(event_id)
    created = []
    for s in settlements_data:
        settlement = EventSettlement(
            event_id=event_id,
            from_member_id=s['from_member_id'],
            to_member_id=s['to_member_id'],
            amount=s['amount'],
        )
        db.session.add(settlement)
        created.append(settlement)

    db.session.commit()
    return jsonify({
        'success': True,
        'data': [s.to_dict() for s in created],
        'message': f'{len(created)} settlement(s) calculated'
    }), 200


@event_settlements_api.route('/<int:settlement_id>', methods=['PUT'])
@token_required
def mark_settlement_completed(current_user, event_id, settlement_id):
    """Mark a settlement as completed."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    settlement = EventSettlement.query.filter_by(id=settlement_id, event_id=event_id).first_or_404()
    settlement.is_completed = True
    settlement.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({
        'success': True,
        'data': settlement.to_dict(),
        'message': 'Settlement marked as completed'
    }), 200
