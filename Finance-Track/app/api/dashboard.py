from datetime import date, timedelta
from flask import Blueprint, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models.expense import Expense
from app.models.income import Income
from app.models.account import Account
from app.models.goal import Goal
from app.models.savings_pot import SavingsPot
from app.models.recurring import RecurringTransaction
from app.utils.decorators import token_required

dashboard_api = Blueprint('dashboard_api', __name__)


@dashboard_api.route('/summary', methods=['GET'])
@token_required
def summary(current_user):
    """
    Get dashboard summary cards
    ---
    tags:
      - Dashboard
    security:
      - Bearer: []
    responses:
      200:
        description: Dashboard summary data
        schema:
          type: object
          properties:
            total_balance:
              type: number
            today_expenses:
              type: number
            today_income:
              type: number
            monthly_expenses:
              type: number
            monthly_income:
              type: number
            savings_rate:
              type: number
            savings_pot_total:
              type: number
            goal_progress:
              type: number
    """
    today = date.today()
    month_start = date(today.year, today.month, 1)

    total_balance = db.session.query(func.sum(Account.balance)).filter(
        Account.user_id == current_user.id, Account.is_active == True
    ).scalar() or 0

    today_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.date == today
    ).scalar() or 0

    today_income = db.session.query(func.sum(Income.amount)).filter(
        Income.user_id == current_user.id, Income.date == today
    ).scalar() or 0

    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.date >= month_start
    ).scalar() or 0

    monthly_income = db.session.query(func.sum(Income.amount)).filter(
        Income.user_id == current_user.id, Income.date >= month_start
    ).scalar() or 0

    savings_rate = ((float(monthly_income) - float(monthly_expenses)) / float(monthly_income) * 100) if float(monthly_income) > 0 else 0

    savings_pot_total = db.session.query(func.sum(SavingsPot.balance)).filter(
        SavingsPot.user_id == current_user.id, SavingsPot.is_active == True
    ).scalar() or 0

    goals = Goal.query.filter_by(user_id=current_user.id, is_completed=False).all()
    avg_goal_progress = 0
    if goals:
        avg_goal_progress = sum(
            (float(g.current_amount) / float(g.target_amount) * 100) if g.target_amount > 0 else 0
            for g in goals
        ) / len(goals)

    return jsonify({
        'success': True,
        'data': {
            'total_balance': float(total_balance),
            'today_expenses': float(today_expenses),
            'today_income': float(today_income),
            'monthly_expenses': float(monthly_expenses),
            'monthly_income': float(monthly_income),
            'savings_rate': round(savings_rate, 1),
            'savings_pot_total': float(savings_pot_total),
            'goal_progress': round(avg_goal_progress, 1),
        }
    }), 200


@dashboard_api.route('/charts', methods=['GET'])
@token_required
def charts(current_user):
    """
    Get dashboard chart data
    ---
    tags:
      - Dashboard
    security:
      - Bearer: []
    responses:
      200:
        description: Chart data for expense categories, income sources, weekly trend, monthly comparison
    """
    from app.models.category import Category
    today = date.today()
    month_start = date(today.year, today.month, 1)

    expense_by_category = db.session.query(
        Expense.category_id,
        Category.name.label('category_name'),
        func.sum(Expense.amount).label('total')
    ).outerjoin(Category, Expense.category_id == Category.id).filter(
        Expense.user_id == current_user.id,
        Expense.date >= month_start,
    ).group_by(Expense.category_id).all()

    income_sources = db.session.query(
        Income.category_id,
        Category.name.label('category_name'),
        func.sum(Income.amount).label('total')
    ).outerjoin(Category, Income.category_id == Category.id).filter(
        Income.user_id == current_user.id,
        Income.date >= month_start,
    ).group_by(Income.category_id).all()

    weekly_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_expense = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id, Expense.date == d
        ).scalar() or 0
        weekly_trend.append({'date': d.isoformat(), 'amount': float(day_expense)})

    monthly_comparison = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        m_start = date(y, m, 1)
        if m == 12:
            m_end = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            m_end = date(y, m + 1, 1) - timedelta(days=1)

        m_exp = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id, Expense.date >= m_start, Expense.date <= m_end
        ).scalar() or 0
        m_inc = db.session.query(func.sum(Income.amount)).filter(
            Income.user_id == current_user.id, Income.date >= m_start, Income.date <= m_end
        ).scalar() or 0
        monthly_comparison.append({
            'month': m_start.strftime('%b %Y'),
            'expenses': float(m_exp),
            'income': float(m_inc),
        })

    return jsonify({
        'success': True,
        'data': {
            'expense_by_category': [{'category_id': c[0], 'category_name': c[1] or 'Uncategorized', 'total': float(c[2])} for c in expense_by_category],
            'income_sources': [{'category_id': c[0], 'category_name': c[1] or 'Uncategorized', 'total': float(c[2])} for c in income_sources],
            'weekly_trend': weekly_trend,
            'monthly_comparison': monthly_comparison,
        }
    }), 200


@dashboard_api.route('/insights', methods=['GET'])
@token_required
def insights(current_user):
    """
    Get smart insights
    ---
    tags:
      - Dashboard
    security:
      - Bearer: []
    responses:
      200:
        description: List of actionable insights
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)

    this_week_exp = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.date >= week_start
    ).scalar() or 0
    last_week_exp = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.date >= last_week_start, Expense.date <= last_week_end
    ).scalar() or 0

    insights_list = []

    if float(last_week_exp) > 0:
        change = ((float(this_week_exp) - float(last_week_exp)) / float(last_week_exp)) * 100
        if change > 20:
            insights_list.append({
                'type': 'warning',
                'message': f'You spent {change:.0f}% more this week compared to last week.',
                'icon': 'trending-up',
            })

    upcoming_recurring = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == current_user.id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.next_due_date <= today + timedelta(days=3),
    ).all()
    for rt in upcoming_recurring:
        days = (rt.next_due_date - today).days
        insights_list.append({
            'type': 'info',
            'message': f'{rt.title} of ₹{float(rt.amount):,.0f} is due in {days} days.',
            'icon': 'clock',
        })

    goals = Goal.query.filter_by(user_id=current_user.id, is_completed=False).all()
    for g in goals:
        if g.deadline:
            days_left = (g.deadline - today).days
            if days_left > 0:
                remaining = float(g.target_amount) - float(g.current_amount)
                monthly_needed = remaining / (days_left / 30)
                insights_list.append({
                    'type': 'info',
                    'message': f'Goal "{g.title}": Need ₹{monthly_needed:,.0f}/month to reach target by deadline.',
                    'icon': 'target',
                })

    return jsonify({'success': True, 'data': insights_list}), 200
