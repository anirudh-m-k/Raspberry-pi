from datetime import date, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models.budget import Budget
from app.models.expense import Expense
from app.models.category import Category
from app.utils.decorators import token_required

budgets_api = Blueprint('budgets_api', __name__)


def get_budget_utilization(budget, user_id):
    """Calculate budget utilization."""
    today = date.today()
    if budget.period == 'monthly':
        start = date(today.year, budget.month or today.month, 1)
        if (budget.month or today.month) == 12:
            end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(today.year, (budget.month or today.month) + 1, 1) - timedelta(days=1)
    else:
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

    query = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= start,
        Expense.date <= end,
    )
    if budget.category_id:
        query = query.filter(Expense.category_id == budget.category_id)

    spent = query.scalar() or 0
    budget_amount = float(budget.amount)
    utilization = (float(spent) / budget_amount * 100) if budget_amount > 0 else 0

    return {
        'spent': float(spent),
        'budget': budget_amount,
        'remaining': budget_amount - float(spent),
        'utilization': round(utilization, 1),
    }


@budgets_api.route('', methods=['GET'])
@token_required
def list_budgets(current_user):
    """
    List budgets with utilization
    ---
    tags:
      - Budgets
    security:
      - Bearer: []
    responses:
      200:
        description: List of budgets with utilization data
    """
    budgets = Budget.query.filter_by(user_id=current_user.id, is_active=True).all()
    result = []
    for b in budgets:
        data = b.to_dict()
        util = get_budget_utilization(b, current_user.id)
        data.update(util)
        result.append(data)
    return jsonify({'success': True, 'data': result}), 200


@budgets_api.route('', methods=['POST'])
@token_required
def create_budget(current_user):
    """
    Create a budget
    ---
    tags:
      - Budgets
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
            - period
          properties:
            category_id:
              type: integer
              description: null for overall budget
            amount:
              type: number
              example: 8000.00
            period:
              type: string
              enum: [weekly, monthly]
            month:
              type: integer
              description: 1-12 for monthly
            year:
              type: integer
            alert_threshold:
              type: integer
              default: 80
              description: Percentage threshold for alerts
            auto_adjust:
              type: boolean
              default: false
    responses:
      201:
        description: Budget created
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'Request body is required'}}), 400

    budget = Budget(
        user_id=current_user.id,
        category_id=data.get('category_id'),
        amount=float(data.get('amount', 0)),
        period=data.get('period', 'monthly'),
        month=data.get('month'),
        year=data.get('year'),
        alert_threshold=data.get('alert_threshold', 80),
        auto_adjust=data.get('auto_adjust', False),
    )
    db.session.add(budget)
    db.session.commit()
    return jsonify({'success': True, 'data': budget.to_dict(), 'message': 'Budget created'}), 201


@budgets_api.route('/<int:budget_id>', methods=['GET'])
@token_required
def get_budget(current_user, budget_id):
    """
    Get budget details with utilization
    ---
    tags:
      - Budgets
    security:
      - Bearer: []
    parameters:
      - name: budget_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Budget details
    """
    budget = Budget.query.get_or_404(budget_id)
    if budget.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    data = budget.to_dict()
    data.update(get_budget_utilization(budget, current_user.id))
    if budget.category_id:
        cat = Category.query.get(budget.category_id)
        data['category_name'] = cat.name if cat else None
    else:
        data['category_name'] = None
    return jsonify({'success': True, 'data': data}), 200


@budgets_api.route('/<int:budget_id>/transactions', methods=['GET'])
@token_required
def get_budget_transactions(current_user, budget_id):
    """
    Get paginated transactions for a budget's category and period
    ---
    tags:
      - Budgets
    security:
      - Bearer: []
    parameters:
      - name: budget_id
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
        description: Paginated transactions
    """
    budget = Budget.query.get_or_404(budget_id)
    if budget.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    today = date.today()
    if budget.period == 'monthly':
        start = date(today.year, budget.month or today.month, 1)
        if (budget.month or today.month) == 12:
            end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(today.year, (budget.month or today.month) + 1, 1) - timedelta(days=1)
    else:
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

    query = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= start,
        Expense.date <= end,
    )
    if budget.category_id:
        query = query.filter(Expense.category_id == budget.category_id)

    query = query.order_by(Expense.date.desc(), Expense.created_at.desc())

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    transactions = []
    for e in pagination.items:
        cat = Category.query.get(e.category_id)
        transactions.append({
            'id': e.id,
            'date': e.date.isoformat(),
            'amount': float(e.amount),
            'category': cat.name if cat else 'Unknown',
            'notes': e.notes or '',
        })

    return jsonify({
        'success': True,
        'data': {
            'transactions': transactions,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
        }
    }), 200


@budgets_api.route('/<int:budget_id>/history', methods=['GET'])
@token_required
def get_budget_history(current_user, budget_id):
    """
    Get historical budget performance for past months/weeks
    ---
    tags:
      - Budgets
    security:
      - Bearer: []
    parameters:
      - name: budget_id
        in: path
        required: true
        type: integer
      - name: months
        in: query
        type: integer
        default: 6
        description: Number of past periods to return
    responses:
      200:
        description: Budget history data
    """
    budget = Budget.query.get_or_404(budget_id)
    if budget.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    num_periods = request.args.get('months', 6, type=int)
    today = date.today()
    history = []

    if budget.period == 'monthly':
        # Loop back N months from current month
        for i in range(1, num_periods + 1):
            # Calculate the target month/year
            target_month = today.month - i
            target_year = today.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1

            # Get start/end dates for that month
            period_start = date(target_year, target_month, 1)
            if target_month == 12:
                period_end = date(target_year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = date(target_year, target_month + 1, 1) - timedelta(days=1)

            # Query expenses for that period
            query = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.date >= period_start,
                Expense.date <= period_end,
            )
            if budget.category_id:
                query = query.filter(Expense.category_id == budget.category_id)

            spent = float(query.scalar() or 0)
            budgeted = float(budget.amount)
            remaining = budgeted - spent
            utilization = (spent / budgeted * 100) if budgeted > 0 else 0

            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            history.append({
                'month': target_month,
                'year': target_year,
                'label': f'{month_names[target_month - 1]} {target_year}',
                'budgeted': budgeted,
                'spent': spent,
                'remaining': remaining,
                'utilization': round(utilization, 1),
            })
    else:
        # Weekly: loop back N weeks
        for i in range(1, num_periods + 1):
            period_end = today - timedelta(days=today.weekday() + 7 * (i - 1))
            period_start = period_end - timedelta(days=6)

            query = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.date >= period_start,
                Expense.date <= period_end,
            )
            if budget.category_id:
                query = query.filter(Expense.category_id == budget.category_id)

            spent = float(query.scalar() or 0)
            budgeted = float(budget.amount)
            remaining = budgeted - spent
            utilization = (spent / budgeted * 100) if budgeted > 0 else 0

            history.append({
                'week_start': period_start.isoformat(),
                'week_end': period_end.isoformat(),
                'label': f'{period_start.strftime("%b %d")} - {period_end.strftime("%b %d")}',
                'budgeted': budgeted,
                'spent': spent,
                'remaining': remaining,
                'utilization': round(utilization, 1),
            })

    return jsonify({
        'success': True,
        'data': {
            'history': history,
        }
    }), 200


@budgets_api.route('/<int:budget_id>', methods=['PUT'])
@token_required
def update_budget(current_user, budget_id):
    """
    Update a budget
    ---
    tags:
      - Budgets
    security:
      - Bearer: []
    parameters:
      - name: budget_id
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
            period:
              type: string
            alert_threshold:
              type: integer
            auto_adjust:
              type: boolean
    responses:
      200:
        description: Budget updated
    """
    budget = Budget.query.get_or_404(budget_id)
    if budget.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403

    data = request.get_json()
    if 'amount' in data:
        budget.amount = float(data['amount'])
    if 'category_id' in data:
        budget.category_id = data['category_id']
    if 'period' in data:
        budget.period = data['period']
    if 'alert_threshold' in data:
        budget.alert_threshold = data['alert_threshold']
    if 'auto_adjust' in data:
        budget.auto_adjust = data['auto_adjust']

    db.session.commit()
    return jsonify({'success': True, 'data': budget.to_dict(), 'message': 'Budget updated'}), 200


@budgets_api.route('/<int:budget_id>', methods=['DELETE'])
@token_required
def delete_budget(current_user, budget_id):
    """
    Delete a budget
    ---
    tags:
      - Budgets
    security:
      - Bearer: []
    parameters:
      - name: budget_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Budget deleted
    """
    budget = Budget.query.get_or_404(budget_id)
    if budget.user_id != current_user.id:
        return jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    db.session.delete(budget)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Budget deleted'}), 200
