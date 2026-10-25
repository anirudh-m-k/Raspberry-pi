from datetime import date
from decimal import Decimal
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.savings_pot import SavingsPot, SavingsPotTransaction
from app.utils.decorators import token_required

savings_pots_api = Blueprint('savings_pots_api', __name__)


@savings_pots_api.route('', methods=['GET'])
@token_required
def list_pots(current_user):
    """
    List savings pots
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    responses:
      200:
        description: List of savings pots
    """
    pots = SavingsPot.query.filter_by(user_id=current_user.id, is_active=True).all()
    return jsonify({'success': True, 'data': [p.to_dict() for p in pots]}), 200


@savings_pots_api.route('', methods=['POST'])
@token_required
def create_pot(current_user):
    """
    Create a savings pot
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
              example: Emergency Fund
            description:
              type: string
            icon:
              type: string
            color:
              type: string
    responses:
      201:
        description: Savings pot created
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    # Optional target_amount (planned save amount) — nullable, validated if provided
    target_amount = data.get('target_amount')
    if target_amount is not None and target_amount != '':
        try:
            target_amount = float(target_amount)
            if target_amount <= 0:
                return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Target amount must be positive'}}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid target amount'}}), 400
    else:
        target_amount = None

    pot = SavingsPot(
        user_id=current_user.id,
        name=data.get('name', ''),
        description=data.get('description'),
        target_amount=target_amount,
        icon=data.get('icon'),
        color=data.get('color'),
    )
    db.session.add(pot)
    db.session.commit()
    return jsonify({'success': True, 'data': pot.to_dict(), 'message': 'Savings pot created'}), 201


@savings_pots_api.route('/<int:pot_id>', methods=['GET'])
@token_required
def get_pot(current_user, pot_id):
    """
    Get pot details with transaction history
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    parameters:
      - name: pot_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Pot details
    """
    pot = SavingsPot.query.get_or_404(pot_id)
    if pot.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = pot.to_dict()
    data['transactions'] = [t.to_dict() for t in pot.transactions.limit(20).all()]
    return jsonify({'success': True, 'data': data}), 200


@savings_pots_api.route('/<int:pot_id>/transactions', methods=['GET'])
@token_required
def get_pot_transactions(current_user, pot_id):
    """
    Get paginated transaction history for a pot
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    parameters:
      - name: pot_id
        in: path
        required: true
        type: integer
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
    responses:
      200:
        description: Paginated transaction list
    """
    pot = SavingsPot.query.get_or_404(pot_id)
    if pot.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = SavingsPotTransaction.query.filter_by(
        pot_id=pot_id, user_id=current_user.id
    ).order_by(
        SavingsPotTransaction.date.desc(),
        SavingsPotTransaction.created_at.desc()
    ).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': {
            'transactions': [t.to_dict() for t in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
        }
    }), 200


@savings_pots_api.route('/<int:pot_id>', methods=['PUT'])
@token_required
def update_pot(current_user, pot_id):
    """
    Update a savings pot
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    parameters:
      - name: pot_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
            description:
              type: string
            icon:
              type: string
            color:
              type: string
    responses:
      200:
        description: Pot updated
    """
    pot = SavingsPot.query.get_or_404(pot_id)
    if pot.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    for field in ['name', 'description', 'icon', 'color']:
        if field in data:
            setattr(pot, field, data[field])
    if 'target_amount' in data:
        val = data.get('target_amount')
        if val is None or val == '':
            pot.target_amount = None
        else:
            try:
                num = float(val)
                if num <= 0:
                    return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Target amount must be positive'}}), 400
                pot.target_amount = num
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid target amount'}}), 400
    db.session.commit()
    return jsonify({'success': True, 'data': pot.to_dict(), 'message': 'Savings pot updated'}), 200


@savings_pots_api.route('/<int:pot_id>', methods=['DELETE'])
@token_required
def delete_pot(current_user, pot_id):
    """
    Delete a pot (soft delete, optionally refund balance)
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    parameters:
      - name: pot_id
        in: path
        required: true
        type: integer
      - name: account_id
        in: query
        type: integer
        description: Account to refund balance to
    responses:
      200:
        description: Pot deleted
    """
    from app.models.account import Account
    pot = SavingsPot.query.get_or_404(pot_id)
    if pot.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    account_id = request.args.get('account_id', type=int)
    if account_id and pot.balance > 0:
        account = Account.query.get(account_id)
        if account and account.user_id == current_user.id:
            account.balance += Decimal(str(pot.balance))

    pot.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'Savings pot deleted'}), 200


@savings_pots_api.route('/<int:pot_id>/deposit', methods=['POST'])
@token_required
def deposit(current_user, pot_id):
    """
    Deposit to a pot (deducts from account if specified)
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    parameters:
      - name: pot_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - amount
          properties:
            amount:
              type: number
              example: 2000.00
            account_id:
              type: integer
            notes:
              type: string
    responses:
      201:
        description: Deposit successful
    """
    from app.models.account import Account
    pot = SavingsPot.query.get_or_404(pot_id)
    if pot.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    amount = float(data.get('amount', 0))
    account_id = data.get('account_id')

    if amount <= 0:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Amount must be positive'}}), 400

    if account_id:
        account = Account.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'Account not found'}}), 404
        if account.balance < Decimal(str(amount)):
            return jsonify({'success': False, 'error': {'code': 'INSUFFICIENT_BALANCE', 'message': 'Insufficient balance in account'}}), 400
        account.balance -= Decimal(str(amount))

    txn = SavingsPotTransaction(
        pot_id=pot.id,
        user_id=current_user.id,
        account_id=account_id,
        amount=amount,
        type='deposit',
        date=date.today(),
        notes=data.get('notes'),
    )
    db.session.add(txn)
    pot.balance += Decimal(str(amount))
    db.session.commit()
    return jsonify({'success': True, 'data': {'transaction': txn.to_dict(), 'pot': pot.to_dict()}, 'message': 'Deposit successful'}), 201


@savings_pots_api.route('/<int:pot_id>/withdraw', methods=['POST'])
@token_required
def withdraw(current_user, pot_id):
    """
    Withdraw from a pot (adds to account if specified)
    ---
    tags:
      - Savings Pots
    security:
      - Bearer: []
    parameters:
      - name: pot_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - amount
          properties:
            amount:
              type: number
            account_id:
              type: integer
            notes:
              type: string
    responses:
      200:
        description: Withdrawal successful
    """
    from app.models.account import Account
    pot = SavingsPot.query.get_or_404(pot_id)
    if pot.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    amount = float(data.get('amount', 0))
    account_id = data.get('account_id')

    if amount <= 0 or amount > float(pot.balance):
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid withdrawal amount'}}), 400

    if account_id:
        account = Account.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'Account not found'}}), 404
        account.balance += Decimal(str(amount))

    txn = SavingsPotTransaction(
        pot_id=pot.id,
        user_id=current_user.id,
        account_id=account_id,
        amount=amount,
        type='withdrawal',
        date=date.today(),
        notes=data.get('notes'),
    )
    db.session.add(txn)
    pot.balance -= Decimal(str(amount))
    db.session.commit()
    return jsonify({'success': True, 'data': {'transaction': txn.to_dict(), 'pot': pot.to_dict()}, 'message': 'Withdrawal successful'}), 200
