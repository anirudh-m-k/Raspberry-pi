from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.expense import Expense
from app.models.account import Account
from app.utils.decorators import token_required

expenses_api = Blueprint('expenses_api', __name__)


@expenses_api.route('', methods=['GET'])
@token_required
def list_expenses(current_user):
    """
    List expenses with filters and pagination
    ---
    tags:
      - Expenses
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
      - name: category_id
        in: query
        type: integer
      - name: date_from
        in: query
        type: string
        format: date
      - name: date_to
        in: query
        type: string
        format: date
      - name: payment_method
        in: query
        type: string
      - name: search
        in: query
        type: string
      - name: sort_by
        in: query
        type: string
        enum: [date, amount, category]
      - name: sort_order
        in: query
        type: string
        enum: [asc, desc]
    responses:
      200:
        description: List of expenses
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category_id = request.args.get('category_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    payment_method = request.args.get('payment_method')
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'date')
    sort_order = request.args.get('sort_order', 'desc')

    query = Expense.query.filter_by(user_id=current_user.id)

    if category_id:
        query = query.filter_by(category_id=category_id)
    if date_from:
        query = query.filter(Expense.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    if date_to:
        query = query.filter(Expense.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    if payment_method:
        query = query.filter_by(payment_method=payment_method)
    if search:
        query = query.filter(
            (Expense.merchant.ilike(f'%{search}%')) |
            (Expense.notes.ilike(f'%{search}%'))
        )

    if sort_by == 'amount':
        order = Expense.amount.desc() if sort_order == 'desc' else Expense.amount.asc()
    elif sort_by == 'category':
        order = Expense.category_id.desc() if sort_order == 'desc' else Expense.category_id.asc()
    else:
        order = Expense.date.desc() if sort_order == 'desc' else Expense.date.asc()

    query = query.order_by(order)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'data': [e.to_dict() for e in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@expenses_api.route('', methods=['POST'])
@token_required
def create_expense(current_user):
    """
    Create a new expense
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - amount
            - date
            - payment_method
          properties:
            amount:
              type: number
              example: 500.00
            date:
              type: string
              format: date
              example: "2026-05-17"
            category_id:
              type: integer
            payment_method:
              type: string
              enum: [Cash, Credit Card, Debit Card, UPI, Net Banking, Wallet]
            account_id:
              type: integer
            merchant:
              type: string
            notes:
              type: string
    responses:
      201:
        description: Expense created
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    amount = data.get('amount')
    if not amount or Decimal(str(amount)) <= 0:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Valid amount is required'}}), 400

    expense = Expense(
        user_id=current_user.id,
        amount=Decimal(str(amount)),
        category_id=data.get('category_id'),
        date=datetime.strptime(data['date'], '%Y-%m-%d').date() if data.get('date') else datetime.utcnow().date(),
        time=datetime.strptime(data['time'], '%H:%M').time() if data.get('time') else None,
        payment_method=data.get('payment_method', 'Cash'),
        account_id=data.get('account_id'),
        merchant=data.get('merchant'),
        notes=data.get('notes'),
    )
    db.session.add(expense)

    if expense.account_id:
        account = Account.query.get(expense.account_id)
        if account and account.user_id == current_user.id:
            account.balance -= Decimal(str(expense.amount))

    db.session.commit()

    return jsonify({
        'success': True,
        'data': expense.to_dict(),
        'message': 'Expense created successfully'
    }), 201


@expenses_api.route('/<int:expense_id>', methods=['GET'])
@token_required
def get_expense(current_user, expense_id):
    """
    Get expense details
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    parameters:
      - name: expense_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Expense details
      403:
        description: Access denied
      404:
        description: Expense not found
    """
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    return jsonify({'success': True, 'data': expense.to_dict()}), 200


@expenses_api.route('/<int:expense_id>', methods=['PUT'])
@token_required
def update_expense(current_user, expense_id):
    """
    Update an expense
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    parameters:
      - name: expense_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            amount:
              type: number
            category_id:
              type: integer
            date:
              type: string
              format: date
            payment_method:
              type: string
            account_id:
              type: integer
            merchant:
              type: string
            notes:
              type: string
    responses:
      200:
        description: Expense updated
      403:
        description: Access denied
    """
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    old_amount = Decimal(str(expense.amount))
    old_account_id = expense.account_id

    if 'amount' in data:
        new_amount = Decimal(str(data['amount']))
        if new_amount <= 0:
            return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Amount must be positive'}}), 400
        expense.amount = new_amount
    if 'category_id' in data:
        expense.category_id = data['category_id']
    if 'date' in data:
        expense.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    if 'time' in data:
        expense.time = datetime.strptime(data['time'], '%H:%M').time() if data['time'] else None
    if 'payment_method' in data:
        expense.payment_method = data['payment_method']
    if 'account_id' in data:
        expense.account_id = data['account_id']
    if 'merchant' in data:
        expense.merchant = data['merchant']
    if 'notes' in data:
        expense.notes = data['notes']

    new_amount = Decimal(str(expense.amount))
    new_account_id = expense.account_id

    if old_account_id:
        old_account = Account.query.get(old_account_id)
        if old_account and old_account.user_id == current_user.id:
            old_account.balance += Decimal(str(old_amount))

    if new_account_id:
        new_account = Account.query.get(new_account_id)
        if new_account and new_account.user_id == current_user.id:
            new_account.balance -= new_amount

    db.session.commit()

    return jsonify({
        'success': True,
        'data': expense.to_dict(),
        'message': 'Expense updated successfully'
    }), 200


@expenses_api.route('/<int:expense_id>', methods=['DELETE'])
@token_required
def delete_expense(current_user, expense_id):
    """
    Delete an expense
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    parameters:
      - name: expense_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Expense deleted
      403:
        description: Access denied
    """
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    if expense.account_id:
        account = Account.query.get(expense.account_id)
        if account and account.user_id == current_user.id:
            account.balance += Decimal(str(expense.amount))

    db.session.delete(expense)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Expense deleted successfully'}), 200


@expenses_api.route('/<int:expense_id>/duplicate', methods=['POST'])
@token_required
def duplicate_expense(current_user, expense_id):
    """
    Duplicate an expense
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    parameters:
      - name: expense_id
        in: path
        required: true
        type: integer
    responses:
      201:
        description: Expense duplicated
    """
    original = Expense.query.get_or_404(expense_id)
    if original.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    duplicate = Expense(
        user_id=current_user.id,
        amount=original.amount,
        category_id=original.category_id,
        date=datetime.utcnow().date(),
        time=original.time,
        payment_method=original.payment_method,
        account_id=original.account_id,
        merchant=original.merchant,
        notes=original.notes,
    )
    db.session.add(duplicate)

    if duplicate.account_id:
        account = Account.query.get(duplicate.account_id)
        if account and account.user_id == current_user.id:
            account.balance -= Decimal(str(duplicate.amount))

    db.session.commit()

    return jsonify({
        'success': True,
        'data': duplicate.to_dict(),
        'message': 'Expense duplicated successfully'
    }), 201


@expenses_api.route('/bulk', methods=['POST'])
@token_required
def bulk_create_expense(current_user):
    """
    Create multiple expenses at once (bulk add)
    ---
    tags:
      - Expenses
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - date
            - expenses
          properties:
            date:
              type: string
              format: date
              example: "2026-06-06"
            expenses:
              type: array
              minItems: 1
              maxItems: 20
              items:
                type: object
                required:
                  - amount
                  - payment_method
                properties:
                  amount:
                    type: number
                    example: 40.00
                  category_id:
                    type: integer
                  payment_method:
                    type: string
                  account_id:
                    type: integer
                  merchant:
                    type: string
                  notes:
                    type: string
    responses:
      201:
        description: Expenses created
      400:
        description: Validation error
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    date_str = data.get('date')
    if not date_str:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Date is required'}}), 400

    try:
        bulk_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid date format. Use YYYY-MM-DD'}}), 400

    expenses_data = data.get('expenses', [])
    if not expenses_data:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'At least one expense is required'}}), 400

    if len(expenses_data) > 20:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Maximum 20 expenses per bulk request'}}), 400

    # Validate all items first
    for i, item in enumerate(expenses_data):
        amount = item.get('amount')
        if not amount:
            return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': f'Amount is required for item {i + 1}'}}), 400
        try:
            if Decimal(str(amount)) <= 0:
                return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': f'Amount must be positive for item {i + 1}'}}), 400
        except Exception:
            return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': f'Invalid amount for item {i + 1}'}}), 400

        if not item.get('payment_method'):
            item['payment_method'] = 'Cash'

    # Create all expenses
    created_expenses = []
    for item in expenses_data:
        expense = Expense(
            user_id=current_user.id,
            amount=Decimal(str(item['amount'])),
            category_id=item.get('category_id'),
            date=bulk_date,
            payment_method=item.get('payment_method', 'Cash'),
            account_id=item.get('account_id'),
            merchant=item.get('merchant'),
            notes=item.get('notes'),
        )
        db.session.add(expense)
        created_expenses.append(expense)

    # Deduct account balances (accumulate per account)
    account_deductions = {}
    for expense in created_expenses:
        if expense.account_id:
            key = expense.account_id
            account_deductions[key] = account_deductions.get(key, Decimal('0')) + expense.amount

    for account_id, total_deduction in account_deductions.items():
        account = Account.query.get(account_id)
        if account and account.user_id == current_user.id:
            account.balance -= total_deduction

    db.session.commit()

    total_amount = sum(float(e.amount) for e in created_expenses)

    return jsonify({
        'success': True,
        'data': {
            'count': len(created_expenses),
            'total': total_amount,
            'date': date_str,
        },
        'message': f'{len(created_expenses)} expenses added successfully'
    }), 201
