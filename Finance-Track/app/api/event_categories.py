from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.event import Event
from app.models.event_category import EventCategory
from app.models.event_participation import EventParticipation
from app.utils.decorators import token_required

event_categories_api = Blueprint('event_categories_api', __name__)


def check_event_ownership(event_id, current_user):
    event = Event.query.get_or_404(event_id)
    is_owner = event.user_id == current_user.id
    is_participant = EventParticipation.query.filter_by(
        event_id=event.id, user_id=current_user.id
    ).first() is not None
    if not (is_owner or is_participant):
        return None, jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return event, None, None


@event_categories_api.route('', methods=['GET'])
@token_required
def list_categories(current_user, event_id):
    """List global defaults + event-specific categories."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code
    categories = EventCategory.query.filter(
        (EventCategory.event_id == None) | (EventCategory.event_id == event_id)  # noqa: E711
    ).order_by(EventCategory.event_id.nullsfirst(), EventCategory.name).all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in categories]}), 200


@event_categories_api.route('', methods=['POST'])
@token_required
def create_category(current_user, event_id):
    """Create an event-specific custom category."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Category name is required'}}), 400

    # Check uniqueness within event
    existing = EventCategory.query.filter_by(event_id=event_id, name=name).first()
    if existing:
        return jsonify({'success': False, 'error': {'code': 'DUPLICATE', 'message': 'Category with this name already exists'}}), 400

    category = EventCategory(
        event_id=event_id,
        name=name,
        icon=data.get('icon'),
        color=data.get('color', '#6366f1'),
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({'success': True, 'data': category.to_dict(), 'message': 'Category created successfully'}), 201


@event_categories_api.route('/<int:category_id>', methods=['PUT'])
@token_required
def update_category(current_user, event_id, category_id):
    """Update an event-specific category."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    category = EventCategory.query.filter_by(id=category_id, event_id=event_id).first_or_404()
    data = request.get_json() or {}

    if 'name' in data and data['name'].strip():
        category.name = data['name'].strip()
    if 'icon' in data:
        category.icon = data['icon']
    if 'color' in data:
        category.color = data['color']

    db.session.commit()
    return jsonify({'success': True, 'data': category.to_dict(), 'message': 'Category updated successfully'}), 200


@event_categories_api.route('/<int:category_id>', methods=['DELETE'])
@token_required
def delete_category(current_user, event_id, category_id):
    """Delete a custom category. Default categories (event_id=None) cannot be deleted."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    category = EventCategory.query.filter_by(id=category_id).first_or_404()
    if category.event_id is None:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Cannot delete default categories'}}), 400
    if category.event_id != event_id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    db.session.delete(category)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Category deleted successfully'}), 200
