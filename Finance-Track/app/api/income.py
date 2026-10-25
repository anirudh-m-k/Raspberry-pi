from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.income import Income
from app.models.account import Account
from app.utils.decorators import token_required

income_api = Blueprint('income_api', __name__)


@income_api.route('', methods=['GET'])
@token_required
def list_income(current_user):
    """
    List income entries with filters and pagination
    ---
    tags:
      - Income
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
      - name: search
        in: query
        type: string
      - name: sort_by
        in: query
        type: string
        enum: [date, amount]
      - name: sort_order
        in: query
        type: string
        enum: [asc, desc]
    responses:
      200:
        description: List of income entries
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category_id = request.args.get('category_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'date')
    sort_order = request.args.get('sort_order', 'desc')

    query = Income.query.filter_by(user_id=current_user.id)

    if category_id:
        query = query.filter_by(category_id=category_id)
    if date_from:
        query = query.filter(Income.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    if date_to:
        query = query.filter(Income.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    if search:
        query = query.filter(
            (Income.source.ilike(f'%{search}%')) |
            (Income.notes.ilike(f'%{search}%'))
        )

    if sort_by == 'amount':
        order = Income.amount.desc() if sort_order == 'desc' else Income.amount.asc()
    else:
        order = Income.date.desc() if sort_order == 'desc' else Income.date.asc()

    query = query.order_by(order)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'data': [i.to_dict() for i in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@income_api.route('', methods=['POST'])
@token_required
def create_income(current_user):
    """
    Create a new income entry
    ---
    tags:
      - Income
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
              example: 50000.00
            source:
              type: string
              example: Monthly Salary
            date:
              type: string
              format: date
              example: "2026-05-17"
            category_id:
              type: integer
            payment_method:
              type: string
              enum: [Cash, Bank Transfer, UPI, Cheque, Wallet]
            account_id:
              type: integer
            notes:
              type: string
    responses:
      201:
        description: Income created
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Valid amount is required'}}), 400

    income = Income(
        user_id=current_user.id,
        amount=Decimal(str(amount)),
        source=data.get('source'),
        category_id=data.get('category_id'),
        date=datetime.strptime(data['date'], '%Y-%m-%d').date() if data.get('date') else datetime.utcnow().date(),
        payment_method=data.get('payment_method', 'Cash'),
        account_id=data.get('account_id'),
        notes=data.get('notes'),
    )
    db.session.add(income)

    if income.account_id:
        account = Account.query.get(income.account_id)
        if account and account.user_id == current_user.id:
            account.balance += Decimal(str(income.amount))

    db.session.commit()

    return jsonify({
        'success': True,
        'data': income.to_dict(),
        'message': 'Income created successfully'
    }), 201


@income_api.route('/<int:income_id>', methods=['GET'])
@token_required
def get_income(current_user, income_id):
    """
    Get income details
    ---
    tags:
      - Income
    security:
      - Bearer: []
    parameters:
      - name: income_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Income details
      403:
        description: Access denied
    """
    income = Income.query.get_or_404(income_id)
    if income.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return jsonify({'success': True, 'data': income.to_dict()}), 200


@income_api.route('/<int:income_id>', methods=['PUT'])
@token_required
def update_income(current_user, income_id):
    """
    Update an income entry
    ---
    tags:
      - Income
    security:
      - Bearer: []
    parameters:
      - name: income_id
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
            source:
              type: string
            category_id:
              type: integer
            date:
              type: string
              format: date
            payment_method:
              type: string
            account_id:
              type: integer
            notes:
              type: string
    responses:
      200:
        description: Income updated
    """
    income = Income.query.get_or_404(income_id)
    if income.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    old_amount = Decimal(str(income.amount))
    old_account_id = income.account_id

    if 'amount' in data:
        new_amount = Decimal(str(data['amount']))
        if new_amount <= 0:
            return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Amount must be positive'}}), 400
        income.amount = new_amount
    if 'source' in data:
        income.source = data['source']
    if 'category_id' in data:
        income.category_id = data['category_id']
    if 'date' in data:
        income.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    if 'payment_method' in data:
        income.payment_method = data['payment_method']
    if 'account_id' in data:
        income.account_id = data['account_id']
    if 'notes' in data:
        income.notes = data['notes']

    new_amount = Decimal(str(income.amount))
    new_account_id = income.account_id

    if old_account_id:
        old_account = Account.query.get(old_account_id)
        if old_account and old_account.user_id == current_user.id:
            old_account.balance -= Decimal(str(old_amount))

    if new_account_id:
        new_account = Account.query.get(new_account_id)
        if new_account and new_account.user_id == current_user.id:
            new_account.balance += new_amount

    db.session.commit()

    return jsonify({
        'success': True,
        'data': income.to_dict(),
        'message': 'Income updated successfully'
    }), 200


@income_api.route('/<int:income_id>', methods=['DELETE'])
@token_required
def delete_income(current_user, income_id):
    """
    Delete an income entry
    ---
    tags:
      - Income
    security:
      - Bearer: []
    parameters:
      - name: income_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Income deleted
    """
    income = Income.query.get_or_404(income_id)
    if income.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    if income.account_id:
        account = Account.query.get(income.account_id)
        if account and account.user_id == current_user.id:
            account.balance -= Decimal(str(income.amount))

    db.session.delete(income)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Income deleted successfully'}), 200
