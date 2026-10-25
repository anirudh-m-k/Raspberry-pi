"""APScheduler job definitions for recurring tasks."""
from datetime import datetime, date, timedelta
from decimal import Decimal


def process_recurring_transactions(app):
    """Process recurring transactions that are due today."""
    with app.app_context():
        from app.models.recurring import RecurringTransaction
        from app.models.expense import Expense
        from app.models.income import Income
        from app.models.account import Account
        from app.models.notification import Notification
        from app.extensions import db
        from app.utils.helpers import get_next_due_date

        today = date.today()
        due_transactions = RecurringTransaction.query.filter(
            RecurringTransaction.next_due_date <= today,
            RecurringTransaction.is_active == True,
            RecurringTransaction.is_paused == False,
        ).all()

        for rt in due_transactions:
            if rt.end_date and rt.end_date < today:
                rt.is_active = False
                continue

            if rt.auto_add:
                if rt.type == 'expense':
                    expense = Expense(
                        user_id=rt.user_id,
                        amount=rt.amount,
                        category_id=rt.category_id,
                        date=today,
                        payment_method=rt.payment_method,
                        account_id=rt.account_id,
                        notes=f'Auto-generated from recurring: {rt.title}',
                        is_recurring_generated=True,
                        recurring_id=rt.id,
                    )
                    db.session.add(expense)
                    if rt.account_id:
                        account = Account.query.get(rt.account_id)
                        if account:
                            account.balance -= Decimal(str(rt.amount))
                else:
                    income = Income(
                        user_id=rt.user_id,
                        amount=rt.amount,
                        category_id=rt.category_id,
                        date=today,
                        payment_method=rt.payment_method,
                        account_id=rt.account_id,
                        notes=f'Auto-generated from recurring: {rt.title}',
                        is_recurring_generated=True,
                        recurring_id=rt.id,
                    )
                    db.session.add(income)
                    if rt.account_id:
                        account = Account.query.get(rt.account_id)
                        if account:
                            account.balance += Decimal(str(rt.amount))

                notification = Notification(
                    user_id=rt.user_id,
                    title=f'Recurring Transaction Added',
                    message=f'{rt.title}: ₹{rt.amount} has been automatically added.',
                    type='salary_credited' if rt.type == 'income' else 'system',
                    related_entity_type='recurring',
                    related_entity_id=rt.id,
                )
                db.session.add(notification)

            rt.next_due_date = get_next_due_date(rt.next_due_date, rt.frequency)

        db.session.commit()


def send_recurring_reminders(app):
    """Send reminders for upcoming recurring transactions."""
    with app.app_context():
        from app.models.recurring import RecurringTransaction
        from app.models.notification import Notification
        from app.extensions import db

        today = date.today()
        upcoming = RecurringTransaction.query.filter(
            RecurringTransaction.is_active == True,
            RecurringTransaction.is_paused == False,
            RecurringTransaction.next_due_date <= today + timedelta(days=3),
        ).all()

        for rt in upcoming:
            days_until = (rt.next_due_date - today).days
            existing = Notification.query.filter(
                Notification.user_id == rt.user_id,
                Notification.type == 'emi_due',
                Notification.related_entity_id == rt.id,
                Notification.created_at >= datetime.utcnow() - timedelta(days=1),
            ).first()

            if not existing:
                notification = Notification(
                    user_id=rt.user_id,
                    title=f'Upcoming: {rt.title}',
                    message=f'{rt.title} of ₹{rt.amount} is due in {days_until} days.',
                    type='emi_due',
                    related_entity_type='recurring',
                    related_entity_id=rt.id,
                )
                db.session.add(notification)

        db.session.commit()


def check_budget_alerts(app):
    """Check budget utilization and send alerts."""
    with app.app_context():
        from app.models.budget import Budget
        from app.models.expense import Expense
        from app.models.notification import Notification
        from app.extensions import db
        from sqlalchemy import func

        today = date.today()
        budgets = Budget.query.filter(
            Budget.is_active == True,
            Budget.period == 'monthly',
        ).all()

        for budget in budgets:
            start = date(today.year, today.month, 1)
            if today.month == 12:
                end = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(today.year, today.month + 1, 1) - timedelta(days=1)

            query = Expense.query.filter(
                Expense.user_id == budget.user_id,
                Expense.date >= start,
                Expense.date <= end,
            )
            if budget.category_id:
                query = query.filter(Expense.category_id == budget.category_id)

            spent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == budget.user_id,
                Expense.date >= start,
                Expense.date <= end,
                Expense.category_id == budget.category_id if budget.category_id else True,
            ).scalar() or 0

            utilization = (float(spent) / float(budget.amount)) * 100 if budget.amount > 0 else 0

            if utilization >= budget.alert_threshold:
                existing = Notification.query.filter(
                    Notification.user_id == budget.user_id,
                    Notification.type == 'budget_exceeded',
                    Notification.related_entity_id == budget.id,
                    Notification.created_at >= datetime.utcnow() - timedelta(days=1),
                ).first()

                if not existing:
                    category_name = budget.category.name if budget.category else 'Overall'
                    notification = Notification(
                        user_id=budget.user_id,
                        title=f'Budget Alert: {category_name}',
                        message=f'You have used {utilization:.0f}% of your {category_name} budget (₹{float(spent):,.0f} / ₹{float(budget.amount):,.0f}).',
                        type='budget_exceeded',
                        related_entity_type='budget',
                        related_entity_id=budget.id,
                    )
                    db.session.add(notification)

        db.session.commit()


def generate_weekly_summary(app):
    """Generate weekly spending summary."""
    with app.app_context():
        from app.models.notification import Notification
        from app.models.expense import Expense
        from app.models.income import Income
        from app.extensions import db
        from sqlalchemy import func

        from app.models.user import User
        users = User.query.filter_by(is_active=True).all()

        for user in users:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            last_week_start = week_start - timedelta(days=7)
            last_week_end = week_start - timedelta(days=1)

            week_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == user.id,
                Expense.date >= last_week_start,
                Expense.date <= last_week_end,
            ).scalar() or 0

            week_income = db.session.query(func.sum(Income.amount)).filter(
                Income.user_id == user.id,
                Income.date >= last_week_start,
                Income.date <= last_week_end,
            ).scalar() or 0

            notification = Notification(
                user_id=user.id,
                title='Weekly Summary',
                message=f'Last week: Income ₹{float(week_income):,.0f}, Expenses ₹{float(week_expenses):,.0f}',
                type='weekly_summary',
            )
            db.session.add(notification)

        db.session.commit()


def generate_monthly_summary(app):
    """Generate monthly spending summary."""
    with app.app_context():
        from app.models.notification import Notification
        from app.models.expense import Expense
        from app.models.income import Income
        from app.extensions import db
        from sqlalchemy import func

        from app.models.user import User
        users = User.query.filter_by(is_active=True).all()

        for user in users:
            today = date.today()
            if today.month == 1:
                last_month_start = date(today.year - 1, 12, 1)
                last_month_end = date(today.year - 1, 12, 31)
            else:
                last_month_start = date(today.year, today.month - 1, 1)
                if today.month - 1 == 12:
                    last_month_end = date(today.year, 12, 31)
                else:
                    last_month_end = date(today.year, today.month, 1) - timedelta(days=1)

            month_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == user.id,
                Expense.date >= last_month_start,
                Expense.date <= last_month_end,
            ).scalar() or 0

            month_income = db.session.query(func.sum(Income.amount)).filter(
                Income.user_id == user.id,
                Income.date >= last_month_start,
                Income.date <= last_month_end,
            ).scalar() or 0

            savings = float(month_income) - float(month_expenses)

            notification = Notification(
                user_id=user.id,
                title='Monthly Summary',
                message=f'Last month: Income ₹{float(month_income):,.0f}, Expenses ₹{float(month_expenses):,.0f}, Savings ₹{savings:,.0f}',
                type='monthly_summary',
            )
            db.session.add(notification)

        db.session.commit()
