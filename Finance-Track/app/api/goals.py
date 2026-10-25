from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.goal import Goal, GoalContribution
from app.utils.decorators import token_required

goals_api = Blueprint('goals_api', __name__)


@goals_api.route('', methods=['GET'])
@token_required
def list_goals(current_user):
    """
    List all goals
    ---
    tags:
      - Goals
    security:
      - Bearer: []
    responses:
      200:
        description: List of goals
    """
    goals = Goal.query.filter_by(user_id=current_user.id).order_by(Goal.created_at.desc()).all()
    return jsonify({'success': True, 'data': [g.to_dict() for g in goals]}), 200


@goals_api.route('', methods=['POST'])
@token_required
def create_goal(current_user):
    """
    Create a new goal
    ---
    tags:
      - Goals
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - title
            - target_amount
          properties:
            title:
              type: string
              example: Vacation
            description:
              type: string
            target_amount:
              type: number
              example: 100000.00
            deadline:
              type: string
              format: date
            priority:
              type: string
              enum: [low, medium, high]
              default: medium
            auto_save_amount:
              type: number
            auto_save_frequency:
              type: string
    responses:
      201:
        description: Goal created
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    goal = Goal(
        user_id=current_user.id,
        title=data.get('title', ''),
        description=data.get('description'),
        target_amount=float(data.get('target_amount', 0)),
        deadline=datetime.strptime(data['deadline'], '%Y-%m-%d').date() if data.get('deadline') else None,
        priority=data.get('priority', 'medium'),
        image_url=data.get('image_url'),
        auto_save_amount=float(data['auto_save_amount']) if data.get('auto_save_amount') else None,
        auto_save_frequency=data.get('auto_save_frequency'),
    )
    db.session.add(goal)
    db.session.commit()
    return jsonify({'success': True, 'data': goal.to_dict(), 'message': 'Goal created'}), 201


@goals_api.route('/<int:goal_id>', methods=['GET'])
@token_required
def get_goal(current_user, goal_id):
    """
    Get goal details with contributions
    ---
    tags:
      - Goals
    security:
      - Bearer: []
    parameters:
      - name: goal_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Goal details
    """
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = goal.to_dict()
    data['contributions'] = [c.to_dict() for c in goal.contributions.limit(20).all()]
    return jsonify({'success': True, 'data': data}), 200


@goals_api.route('/<int:goal_id>', methods=['PUT'])
@token_required
def update_goal(current_user, goal_id):
    """
    Update a goal
    ---
    tags:
      - Goals
    security:
      - Bearer: []
    parameters:
      - name: goal_id
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
            description:
              type: string
            target_amount:
              type: number
            deadline:
              type: string
              format: date
            priority:
              type: string
            auto_save_amount:
              type: number
            auto_save_frequency:
              type: string
    responses:
      200:
        description: Goal updated
    """
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    for field in ['title', 'description', 'priority', 'image_url']:
        if field in data:
            setattr(goal, field, data[field])
    if 'target_amount' in data:
        goal.target_amount = float(data['target_amount'])
    if 'deadline' in data:
        goal.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date() if data['deadline'] else None
    if 'auto_save_amount' in data:
        goal.auto_save_amount = float(data['auto_save_amount']) if data['auto_save_amount'] else None
    if 'auto_save_frequency' in data:
        goal.auto_save_frequency = data['auto_save_frequency']

    db.session.commit()
    return jsonify({'success': True, 'data': goal.to_dict(), 'message': 'Goal updated'}), 200


@goals_api.route('/<int:goal_id>', methods=['DELETE'])
@token_required
def delete_goal(current_user, goal_id):
    """
    Delete a goal and refund contributions
    ---
    tags:
      - Goals
    security:
      - Bearer: []
    parameters:
      - name: goal_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Goal deleted with refund
    """
    from app.models.account import Account
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    contributions = GoalContribution.query.filter_by(goal_id=goal.id).all()
    for contrib in contributions:
        if contrib.account_id:
            account = Account.query.get(contrib.account_id)
            if account and account.user_id == current_user.id:
                if contrib.type == 'withdrawal':
                    account.balance -= Decimal(str(contrib.amount))
                else:
                    account.balance += Decimal(str(contrib.amount))

    GoalContribution.query.filter_by(goal_id=goal.id).delete()
    db.session.delete(goal)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Goal deleted and contributions refunded'}), 200


@goals_api.route('/<int:goal_id>/contribute', methods=['POST'])
@token_required
def contribute(current_user, goal_id):
    """
    Contribute to a goal (deducts from account if specified)
    ---
    tags:
      - Goals
    security:
      - Bearer: []
    parameters:
      - name: goal_id
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
              example: 5000.00
            account_id:
              type: integer
              description: Account to deduct from
            notes:
              type: string
    responses:
      201:
        description: Contribution added
      400:
        description: Insufficient balance
    """
    from app.models.account import Account
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
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

    contribution = GoalContribution(
        goal_id=goal.id,
        user_id=current_user.id,
        account_id=account_id,
        amount=amount,
        type=data.get('type', 'manual'),
        date=datetime.strptime(data.get('date', ''), '%Y-%m-%d').date() if data.get('date') else date.today(),
        notes=data.get('notes'),
    )
    db.session.add(contribution)

    goal.current_amount += Decimal(str(amount))
    if goal.current_amount >= goal.target_amount:
        goal.is_completed = True
        goal.completed_at = datetime.utcnow()

    db.session.commit()
    return jsonify({'success': True, 'data': {'contribution': contribution.to_dict(), 'goal': goal.to_dict()}, 'message': 'Contribution added'}), 201


@goals_api.route('/<int:goal_id>/withdraw', methods=['POST'])
@token_required
def withdraw(current_user, goal_id):
    """
    Withdraw from a goal (adds to account if specified)
    ---
    tags:
      - Goals
    security:
      - Bearer: []
    parameters:
      - name: goal_id
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
              description: Account to add to
            notes:
              type: string
    responses:
      200:
        description: Withdrawal successful
    """
    from app.models.account import Account
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    amount = float(data.get('amount', 0))
    account_id = data.get('account_id')

    if amount <= 0 or amount > float(goal.current_amount):
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid withdrawal amount'}}), 400

    if account_id:
        account = Account.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': 'Account not found'}}), 404
        account.balance += Decimal(str(amount))

    contribution = GoalContribution(
        goal_id=goal.id,
        user_id=current_user.id,
        account_id=account_id,
        amount=-amount,
        type='withdrawal',
        date=date.today(),
        notes=data.get('notes'),
    )
    db.session.add(contribution)
    goal.current_amount -= Decimal(str(amount))
    goal.is_completed = False
    db.session.commit()

    return jsonify({'success': True, 'data': {'contribution': contribution.to_dict(), 'goal': goal.to_dict()}, 'message': 'Withdrawal successful'}), 200
