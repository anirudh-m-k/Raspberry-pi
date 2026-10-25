from datetime import datetime
from decimal import Decimal
import json
from flask import Blueprint, request, jsonify, send_file
from app.extensions import db
from app.models.event import Event
from app.models.event_expense import EventExpense
from app.models.event_expense_split import EventExpenseSplit
from app.models.event_participation import EventParticipation
from app.utils.decorators import token_required
from app.services.split_service import SplitService
from app.services.event_service import EventService

event_expenses_api = Blueprint('event_expenses_api', __name__)


def check_event_ownership(event_id, current_user):
    event = Event.query.get_or_404(event_id)
    is_owner = event.user_id == current_user.id
    is_participant = EventParticipation.query.filter_by(
        event_id=event.id, user_id=current_user.id
    ).first() is not None
    if not (is_owner or is_participant):
        return None, jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return event, None, None


def get_payload():
    """Extract dict payload from JSON body or multipart/form-data."""
    if request.is_json and request.get_json():
        return request.get_json()
    data = {}
    for k, v in request.form.items():
        if k in ('splits', 'tags'):
            try:
                data[k] = json.loads(v)
            except Exception:
                data[k] = []
        else:
            data[k] = v
    return data


@event_expenses_api.route('', methods=['GET'])
@token_required
def list_expenses(current_user, event_id):
    """List event expenses with filters."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category_id = request.args.get('category_id', type=int)
    member_id = request.args.get('paid_by_member_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'date')
    sort_order = request.args.get('sort_order', 'desc')

    query = EventExpense.query.filter_by(event_id=event_id)

    if category_id:
        query = query.filter_by(category_id=category_id)
    if member_id:
        query = query.filter_by(paid_by_member_id=member_id)
    if date_from:
        query = query.filter(EventExpense.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    if date_to:
        query = query.filter(EventExpense.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    if search:
        query = query.filter(
            (EventExpense.note.ilike(f'%{search}%')) |
            (EventExpense.description.ilike(f'%{search}%')) |
            (EventExpense.merchant.ilike(f'%{search}%'))
        )

    if sort_by == 'amount':
        order = EventExpense.amount.desc() if sort_order == 'desc' else EventExpense.amount.asc()
    else:
        order = EventExpense.date.desc() if sort_order == 'desc' else EventExpense.date.asc()

    query = query.order_by(order)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'data': [e.to_short_dict() for e in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@event_expenses_api.route('/download-bills', methods=['GET'])
@token_required
def download_bills(current_user, event_id):
    """Download all receipts/bills of an event packaged in a ZIP file."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    buffer, filename, count = EventService.export_event_bills_zip(event_id)
    if count == 0:
        return jsonify({'success': False, 'error': {'code': 'NO_BILLS', 'message': 'No bills found for this event'}}), 404

    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )


@event_expenses_api.route('', methods=['POST'])
@token_required
def create_expense(current_user, event_id):
    """Create an event expense and auto-generate splits."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    data = get_payload()
    amount = data.get('amount')
    if not amount or Decimal(str(amount)) <= 0:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Valid amount is required'}}), 400

    paid_by = data.get('paid_by_member_id') or data.get('paid_by_id')
    if not paid_by:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'paid_by_member_id is required'}}), 400

    date_str = data.get('date')
    if not date_str:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Date is required'}}), 400

    split_type = data.get('split_type', 'equal')
    from app.utils.constants import SPLIT_TYPES
    if split_type not in SPLIT_TYPES:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': f'split_type must be one of {SPLIT_TYPES}'}}), 400

    expense = EventExpense(
        event_id=event_id,
        amount=Decimal(str(amount)),
        category_id=int(data['category_id']) if data.get('category_id') else None,
        paid_by_member_id=int(paid_by),
        date=datetime.strptime(str(date_str), '%Y-%m-%d').date(),
        note=data.get('note'),
        description=data.get('description'),
        merchant=data.get('merchant'),
        location=data.get('location'),
        receipt_image=data.get('receipt_image'),
        tags=','.join(data['tags']) if isinstance(data.get('tags'), list) else data.get('tags'),
        split_type=split_type,
    )
    db.session.add(expense)
    db.session.flush()  # get expense.id

    # Handle receipt file upload if provided
    file_obj = request.files.get('receipt_file') or request.files.get('file') or request.files.get('receipt')
    if file_obj:
        receipt_url = EventService.save_expense_receipt(current_user, event, expense, file_obj)
        if receipt_url:
            expense.receipt_image = receipt_url

    split_data = data.get('splits')
    SplitService.create_splits_for_expense(expense, split_data)

    db.session.commit()
    return jsonify({
        'success': True,
        'data': expense.to_dict(),
        'message': 'Expense created successfully'
    }), 201


@event_expenses_api.route('/<int:expense_id>', methods=['GET'])
@token_required
def get_expense(current_user, event_id, expense_id):
    """Get expense details with splits."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code
    expense = EventExpense.query.filter_by(id=expense_id, event_id=event_id).first_or_404()
    return jsonify({'success': True, 'data': expense.to_dict()}), 200


@event_expenses_api.route('/<int:expense_id>', methods=['PUT'])
@token_required
def update_expense(current_user, event_id, expense_id):
    """Update an expense and recalculate splits."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    expense = EventExpense.query.filter_by(id=expense_id, event_id=event_id).first_or_404()
    data = get_payload()

    if 'amount' in data:
        if Decimal(str(data['amount'])) <= 0:
            return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Amount must be positive'}}), 400
        expense.amount = Decimal(str(data['amount']))
    if 'category_id' in data:
        expense.category_id = int(data['category_id']) if data['category_id'] else None
    if 'paid_by_member_id' in data or 'paid_by_id' in data:
        expense.paid_by_member_id = int(data.get('paid_by_member_id') or data.get('paid_by_id'))
    if 'date' in data:
        expense.date = datetime.strptime(str(data['date']), '%Y-%m-%d').date()
    if 'note' in data:
        expense.note = data['note']
    if 'description' in data:
        expense.description = data['description']
    if 'merchant' in data:
        expense.merchant = data['merchant']
    if 'location' in data:
        expense.location = data['location']
    if 'split_type' in data:
        expense.split_type = data['split_type']
    if 'tags' in data:
        expense.tags = ','.join(data['tags']) if isinstance(data.get('tags'), list) else data.get('tags')

    # Handle receipt file upload if provided
    file_obj = request.files.get('receipt_file') or request.files.get('file') or request.files.get('receipt')
    if file_obj:
        receipt_url = EventService.save_expense_receipt(current_user, event, expense, file_obj)
        if receipt_url:
            expense.receipt_image = receipt_url

    # Replace splits
    SplitService.delete_splits_for_expense(expense.id)
    split_data = data.get('splits')
    SplitService.create_splits_for_expense(expense, split_data)

    db.session.commit()
    return jsonify({
        'success': True,
        'data': expense.to_dict(),
        'message': 'Expense updated successfully'
    }), 200


@event_expenses_api.route('/<int:expense_id>', methods=['DELETE'])
@token_required
def delete_expense(current_user, event_id, expense_id):
    """Delete an expense (splits cascade)."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code
    expense = EventExpense.query.filter_by(id=expense_id, event_id=event_id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Expense deleted successfully'}), 200

