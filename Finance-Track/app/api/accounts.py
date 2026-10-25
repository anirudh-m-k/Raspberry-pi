from decimal import Decimal
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.account import Account
from app.utils.decorators import token_required

accounts_api = Blueprint('accounts_api', __name__)


@accounts_api.route('', methods=['GET'])
@token_required
def list_accounts(current_user):
    """
    List all accounts
    ---
    tags:
      - Accounts
    security:
      - Bearer: []
    responses:
      200:
        description: List of accounts
    """
    accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
    return jsonify({
        'success': True,
        'data': [a.to_dict() for a in accounts]
    }), 200


@accounts_api.route('', methods=['POST'])
@token_required
def create_account(current_user):
    """
    Create a new account
    ---
    tags:
      - Accounts
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
            - type
          properties:
            name:
              type: string
              example: SBI Savings
            type:
              type: string
              enum: [cash, bank, credit_card, upi, wallet, investment]
            balance:
              type: number
              example: 10000.00
            currency:
              type: string
              default: INR
            institution:
              type: string
            notes:
              type: string
    responses:
      201:
        description: Account created
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    name = data.get('name', '').strip()
    account_type = data.get('type', '').strip()
    if not name or not account_type:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Name and type are required'}}), 400

    account = Account(
        user_id=current_user.id,
        name=name,
        type=account_type,
        balance=Decimal(str(data.get('balance', 0))),
        currency=data.get('currency', 'INR'),
        institution=data.get('institution'),
        notes=data.get('notes'),
    )
    db.session.add(account)
    db.session.commit()

    return jsonify({
        'success': True,
        'data': account.to_dict(),
        'message': 'Account created successfully'
    }), 201


@accounts_api.route('/<int:account_id>', methods=['GET'])
@token_required
def get_account(current_user, account_id):
    """
    Get account details
    ---
    tags:
      - Accounts
    security:
      - Bearer: []
    parameters:
      - name: account_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Account details
    """
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return jsonify({'success': True, 'data': account.to_dict()}), 200


@accounts_api.route('/<int:account_id>', methods=['PUT'])
@token_required
def update_account(current_user, account_id):
    """
    Update an account
    ---
    tags:
      - Accounts
    security:
      - Bearer: []
    parameters:
      - name: account_id
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
            type:
              type: string
            balance:
              type: number
            currency:
              type: string
            institution:
              type: string
            notes:
              type: string
    responses:
      200:
        description: Account updated
    """
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    if 'name' in data:
        account.name = data['name']
    if 'type' in data:
        account.type = data['type']
    if 'balance' in data:
        account.balance = Decimal(str(data['balance']))
    if 'currency' in data:
        account.currency = data['currency']
    if 'institution' in data:
        account.institution = data['institution']
    if 'notes' in data:
        account.notes = data['notes']
    if 'is_hidden' in data:
        account.is_hidden = data['is_hidden']

    db.session.commit()

    return jsonify({
        'success': True,
        'data': account.to_dict(),
        'message': 'Account updated successfully'
    }), 200


@accounts_api.route('/<int:account_id>', methods=['DELETE'])
@token_required
def delete_account(current_user, account_id):
    """
    Delete an account (soft delete)
    ---
    tags:
      - Accounts
    security:
      - Bearer: []
    parameters:
      - name: account_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Account deleted
    """
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    account.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'Account deleted successfully'}), 200


@accounts_api.route('/transfer', methods=['POST'])
@token_required
def transfer(current_user):
    """
    Transfer between accounts
    ---
    tags:
      - Accounts
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - from_account_id
            - to_account_id
            - amount
          properties:
            from_account_id:
              type: integer
            to_account_id:
              type: integer
            amount:
              type: number
    responses:
      200:
        description: Transfer successful
      400:
        description: Insufficient balance
    """
    data = request.get_json()
    from_id = data.get('from_account_id')
    to_id = data.get('to_account_id')
    amount = Decimal(str(data.get('amount', 0)))

    if not from_id or not to_id or amount <= 0:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Valid from_account_id, to_account_id, and amount are required'}}), 400

    if from_id == to_id:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Cannot transfer to the same account'}}), 400

    from_account = Account.query.get_or_404(from_id)
    to_account = Account.query.get_or_404(to_id)
    db.session.refresh(from_account)  # BIZ-01: Get latest balance to mitigate TOCTOU

    if from_account.user_id != current_user.id or to_account.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    if from_account.balance < Decimal(str(amount)):
        return jsonify({'success': False, 'error': {'code': 'INSUFFICIENT_BALANCE', 'message': 'Insufficient balance in source account'}}), 400

    from_account.balance -= Decimal(str(amount))
    to_account.balance += Decimal(str(amount))
    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'from_account': from_account.to_dict(),
            'to_account': to_account.to_dict(),
            'amount': amount,
        },
        'message': 'Transfer successful'
    }), 200
