from datetime import datetime
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.recurring import RecurringTransaction
from app.utils.decorators import token_required
from app.utils.helpers import get_next_due_date

recurring_api = Blueprint('recurring_api', __name__)


@recurring_api.route('', methods=['GET'])
@token_required
def list_recurring(current_user):
    """
    List recurring transactions
    ---
    tags:
      - Recurring
    security:
      - Bearer: []
    parameters:
      - name: type
        in: query
        type: string
        enum: [expense, income]
    responses:
      200:
        description: List of recurring transactions
    """
    type_filter = request.args.get('type')
    query = RecurringTransaction.query.filter_by(user_id=current_user.id)
    if type_filter:
        query = query.filter_by(type=type_filter)
    items = query.order_by(RecurringTransaction.next_due_date.asc()).all()
    return jsonify({'success': True, 'data': [r.to_dict() for r in items]}), 200


@recurring_api.route('', methods=['POST'])
@token_required
def create_recurring(current_user):
    """
    Create a recurring transaction
    ---
    tags:
      - Recurring
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - type
            - title
            - amount
            - frequency
            - payment_method
            - start_date
          properties:
            type:
              type: string
              enum: [expense, income]
            title:
              type: string
              example: Netflix
            amount:
              type: number
              example: 500.00
            category_id:
              type: integer
            frequency:
              type: string
              enum: [daily, weekly, monthly, quarterly, yearly]
            payment_method:
              type: string
            account_id:
              type: integer
            start_date:
              type: string
              format: date
            end_date:
              type: string
              format: date
            auto_add:
              type: boolean
              default: true
            reminder_days_before:
              type: integer
              default: 3
            notes:
              type: string
    responses:
      201:
        description: Recurring transaction created
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    rt = RecurringTransaction(
        user_id=current_user.id,
        type=data.get('type', 'expense'),
        title=data.get('title', ''),
        amount=float(data.get('amount', 0)),
        category_id=data.get('category_id'),
        frequency=data.get('frequency', 'monthly'),
        payment_method=data.get('payment_method', 'Cash'),
        account_id=data.get('account_id'),
        start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
        end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None,
        next_due_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
        auto_add=data.get('auto_add', True),
        reminder_days_before=data.get('reminder_days_before', 3),
        notes=data.get('notes'),
    )
    db.session.add(rt)
    db.session.commit()

    return jsonify({'success': True, 'data': rt.to_dict(), 'message': 'Recurring transaction created'}), 201


@recurring_api.route('/<int:rt_id>', methods=['GET'])
@token_required
def get_recurring(current_user, rt_id):
    """
    Get recurring transaction details
    ---
    tags:
      - Recurring
    security:
      - Bearer: []
    parameters:
      - name: rt_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Recurring transaction details
    """
    rt = RecurringTransaction.query.get_or_404(rt_id)
    if rt.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return jsonify({'success': True, 'data': rt.to_dict()}), 200


@recurring_api.route('/<int:rt_id>', methods=['PUT'])
@token_required
def update_recurring(current_user, rt_id):
    """
    Update a recurring transaction
    ---
    tags:
      - Recurring
    security:
      - Bearer: []
    parameters:
      - name: rt_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            title:
              type: string
            amount:
              type: number
            category_id:
              type: integer
            frequency:
              type: string
            payment_method:
              type: string
            account_id:
              type: integer
            auto_add:
              type: boolean
            reminder_days_before:
              type: integer
            notes:
              type: string
    responses:
      200:
        description: Recurring transaction updated
    """
    rt = RecurringTransaction.query.get_or_404(rt_id)
    if rt.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    for field in ['title', 'amount', 'category_id', 'frequency', 'payment_method', 'account_id', 'auto_add', 'reminder_days_before', 'notes']:
        if field in data:
            setattr(rt, field, float(data[field]) if field == 'amount' else data[field])
    if 'start_date' in data:
        rt.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    if 'end_date' in data:
        rt.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data['end_date'] else None

    db.session.commit()
    return jsonify({'success': True, 'data': rt.to_dict(), 'message': 'Recurring transaction updated'}), 200


@recurring_api.route('/<int:rt_id>', methods=['DELETE'])
@token_required
def delete_recurring(current_user, rt_id):
    """
    Delete a recurring transaction
    ---
    tags:
      - Recurring
    security:
      - Bearer: []
    parameters:
      - name: rt_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Recurring transaction deleted
    """
    rt = RecurringTransaction.query.get_or_404(rt_id)
    if rt.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    db.session.delete(rt)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Recurring transaction deleted'}), 200


@recurring_api.route('/<int:rt_id>/pause', methods=['POST'])
@token_required
def toggle_pause(current_user, rt_id):
    """
    Pause or resume a recurring transaction
    ---
    tags:
      - Recurring
    security:
      - Bearer: []
    parameters:
      - name: rt_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Status updated
    """
    rt = RecurringTransaction.query.get_or_404(rt_id)
    if rt.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    rt.is_paused = not rt.is_paused
    db.session.commit()
    status = 'paused' if rt.is_paused else 'resumed'
    return jsonify({'success': True, 'data': rt.to_dict(), 'message': f'Recurring transaction {status}'}), 200


@recurring_api.route('/<int:rt_id>/skip', methods=['POST'])
@token_required
def skip_next(current_user, rt_id):
    """
    Skip the next occurrence
    ---
    tags:
      - Recurring
    security:
      - Bearer: []
    parameters:
      - name: rt_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Next occurrence skipped
    """
    rt = RecurringTransaction.query.get_or_404(rt_id)
    if rt.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    rt.next_due_date = get_next_due_date(rt.next_due_date, rt.frequency)
    db.session.commit()
    return jsonify({'success': True, 'data': rt.to_dict(), 'message': 'Next occurrence skipped'}), 200
