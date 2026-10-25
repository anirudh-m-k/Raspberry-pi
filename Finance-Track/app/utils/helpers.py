from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta


def get_next_due_date(current_date, frequency):
    """Calculate the next due date based on frequency."""
    if frequency == 'daily':
        return current_date + timedelta(days=1)
    elif frequency == 'weekly':
        return current_date + timedelta(weeks=1)
    elif frequency == 'monthly':
        return current_date + relativedelta(months=1)
    elif frequency == 'quarterly':
        return current_date + relativedelta(months=3)
    elif frequency == 'yearly':
        return current_date + relativedelta(years=1)
    return current_date + timedelta(days=1)


def get_month_start_end(year=None, month=None):
    """Get the start and end dates of a month."""
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def get_week_start_end(offset=0):
    """Get the start and end dates of the week (Monday to Sunday)."""
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def format_amount(amount):
    """Format amount with Indian currency symbol."""
    try:
        return f"₹{float(amount):,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"
