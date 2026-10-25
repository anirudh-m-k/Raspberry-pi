from datetime import date, datetime
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.expense import Expense
from app.models.income import Income
from app.models.recurring import RecurringTransaction
from app.models.goal import Goal
from app.utils.decorators import token_required

calendar_api = Blueprint('calendar_api', __name__)


@calendar_api.route('/events', methods=['GET'])
@token_required
def get_events(current_user):
    """
    Get calendar events for a date range
    ---
    tags:
      - Calendar
    security:
      - Bearer: []
    parameters:
      - name: start
        in: query
        type: string
        format: date
        required: true
      - name: end
        in: query
        type: string
        format: date
        required: true
    responses:
      200:
        description: Calendar events (expenses, income, recurring due dates, goal deadlines)
    """
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    if not start_str or not end_str:
        today = date.today()
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year + 1, 1, 1)
        else:
            end = date(today.year, today.month + 1, 1)
    else:
        start = datetime.strptime(start_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_str, '%Y-%m-%d').date()

    events = []

    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= start,
        Expense.date <= end,
    ).all()
    for e in expenses:
        events.append({
            'date': e.date.isoformat(),
            'type': 'expense',
            'title': f'Expense: ₹{float(e.amount):,.0f}',
            'description': e.merchant or e.notes or '',
            'amount': float(e.amount),
            'category': e.category.name if e.category else None,
            'color': '#ef4444',
        })

    incomes = Income.query.filter(
        Income.user_id == current_user.id,
        Income.date >= start,
        Income.date <= end,
    ).all()
    for i in incomes:
        events.append({
            'date': i.date.isoformat(),
            'type': 'income',
            'title': f'Income: ₹{float(i.amount):,.0f}',
            'description': i.source or '',
            'amount': float(i.amount),
            'category': i.category.name if i.category else None,
            'color': '#22c55e',
        })

    recurring = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == current_user.id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.next_due_date >= start,
        RecurringTransaction.next_due_date <= end,
    ).all()
    for r in recurring:
        events.append({
            'date': r.next_due_date.isoformat(),
            'type': 'recurring',
            'title': f'{r.title}: ₹{float(r.amount):,.0f}',
            'description': f'{r.frequency} - {r.type}',
            'amount': float(r.amount),
            'color': '#f59e0b',
        })

    goals = Goal.query.filter(
        Goal.user_id == current_user.id,
        Goal.deadline != None,
        Goal.is_completed == False,
        Goal.deadline >= start,
        Goal.deadline <= end,
    ).all()
    for g in goals:
        events.append({
            'date': g.deadline.isoformat(),
            'type': 'goal_deadline',
            'title': f'Goal Deadline: {g.title}',
            'description': f'Target: ₹{float(g.target_amount):,.0f}',
            'color': '#8b5cf6',
        })

    return jsonify({'success': True, 'data': events}), 200
