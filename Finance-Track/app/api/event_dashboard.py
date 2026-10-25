from flask import Blueprint, jsonify
from app.models.event import Event
from app.models.event_participation import EventParticipation
from app.utils.decorators import token_required
from app.services.event_service import EventService

event_dashboard_api = Blueprint('event_dashboard_api', __name__)


def can_access_event(event, user_id):
    """Return True if user is the event owner OR a participant."""
    if event.user_id == user_id:
        return True
    return EventParticipation.query.filter_by(
        event_id=event.id, user_id=user_id
    ).first() is not None


@event_dashboard_api.route('', methods=['GET'])
@token_required
def get_dashboard(current_user, event_id):
    """Get full dashboard data for an event."""
    event = Event.query.get_or_404(event_id)
    if not can_access_event(event, current_user.id):
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    try:
        data = EventService.get_dashboard(event_id)
    except Exception as e:
        return jsonify({'success': False, 'error': {'code': 'INTERNAL_ERROR', 'message': str(e)}}), 500

    return jsonify({'success': True, 'data': data}), 200
