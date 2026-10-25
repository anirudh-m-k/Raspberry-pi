from datetime import date, timedelta
from flask import Blueprint, request, jsonify, send_file
from sqlalchemy import func
from app.extensions import db
from app.models.expense import Expense
from app.models.income import Income
from app.models.category import Category
from app.utils.decorators import token_required
from app.services.export_service import generate_pdf_report
import io
import csv

reports_api = Blueprint('reports_api', __name__)


def get_date_range(period, year=None, month=None):
    today = date.today()
    if period == 'daily':
        return today, today
    elif period == 'weekly':
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    elif period == 'monthly':
        y = year or today.year
        m = month or today.month
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(y, m + 1, 1) - timedelta(days=1)
        return start, end
    elif period == 'yearly':
        y = year or today.year
        return date(y, 1, 1), date(y, 12, 31)
    return today, today


@reports_api.route('/spending', methods=['GET'])
@token_required
def spending_report(current_user):
    """
    Get spending breakdown by category
    ---
    tags:
      - Reports
    security:
      - Bearer: []
    parameters:
      - name: period
        in: query
        type: string
        enum: [daily, weekly, monthly, yearly]
        default: monthly
      - name: year
        in: query
        type: integer
      - name: month
        in: query
        type: integer
    responses:
      200:
        description: Spending breakdown
    """
    from app.models.category import Category
    period = request.args.get('period', 'monthly')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    start, end = get_date_range(period, year, month)

    breakdown = db.session.query(
        Expense.category_id,
        Category.name.label('category_name'),
        func.sum(Expense.amount).label('total'),
        func.count(Expense.id).label('count')
    ).outerjoin(Category, Expense.category_id == Category.id).filter(
        Expense.user_id == current_user.id,
        Expense.date >= start,
        Expense.date <= end,
    ).group_by(Expense.category_id).all()

    total = sum(float(b[2]) for b in breakdown)

    return jsonify({
        'success': True,
        'data': {
            'period': period,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'total': total,
            'breakdown': [{'category_id': b[0], 'category_name': b[1] or 'Uncategorized', 'total': float(b[2]), 'count': b[3], 'percentage': round(float(b[2]) / total * 100, 1) if total > 0 else 0} for b in breakdown],
        }
    }), 200


@reports_api.route('/income-expense', methods=['GET'])
@token_required
def income_expense_report(current_user):
    """
    Get income vs expense comparison
    ---
    tags:
      - Reports
    security:
      - Bearer: []
    parameters:
      - name: period
        in: query
        type: string
        enum: [daily, weekly, monthly, yearly]
    responses:
      200:
        description: Income vs expense data
    """
    period = request.args.get('period', 'monthly')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    start, end = get_date_range(period, year, month)

    total_expense = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.date >= start, Expense.date <= end
    ).scalar() or 0

    total_income = db.session.query(func.sum(Income.amount)).filter(
        Income.user_id == current_user.id, Income.date >= start, Income.date <= end
    ).scalar() or 0

    return jsonify({
        'success': True,
        'data': {
            'period': period,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'income': float(total_income),
            'expense': float(total_expense),
            'net': float(total_income) - float(total_expense),
            'savings_rate': round((float(total_income) - float(total_expense)) / float(total_income) * 100, 1) if float(total_income) > 0 else 0,
        }
    }), 200


@reports_api.route('/savings', methods=['GET'])
@token_required
def savings_report(current_user):
    """
    Get savings ratio trend (last 6 months)
    ---
    tags:
      - Reports
    security:
      - Bearer: []
    responses:
      200:
        description: Savings trend data
    """
    today = date.today()
    result = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(y, m + 1, 1) - timedelta(days=1)

        exp = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id, Expense.date >= start, Expense.date <= end
        ).scalar() or 0
        inc = db.session.query(func.sum(Income.amount)).filter(
            Income.user_id == current_user.id, Income.date >= start, Income.date <= end
        ).scalar() or 0

        savings = float(inc) - float(exp)
        rate = round(savings / float(inc) * 100, 1) if float(inc) > 0 else 0

        result.append({
            'month': start.strftime('%b %Y'),
            'income': float(inc),
            'expense': float(exp),
            'savings': savings,
            'savings_rate': rate,
        })

    return jsonify({'success': True, 'data': result}), 200


@reports_api.route('/heatmap', methods=['GET'])
@token_required
def heatmap(current_user):
    """
    Get spending heatmap data (day of week)
    ---
    tags:
      - Reports
    security:
      - Bearer: []
    responses:
      200:
        description: Heatmap data by day of week
    """
    today = date.today()
    start = today - timedelta(days=90)

    expenses = db.session.query(
        func.strftime('%w', Expense.date).label('day_of_week'),
        func.sum(Expense.amount).label('total')
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= start,
    ).group_by('day_of_week').all()

    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    result = [{'day': days[int(e[0])], 'total': float(e[1])} for e in expenses]

    return jsonify({'success': True, 'data': result}), 200


@reports_api.route('/export', methods=['GET'])
@token_required
def export_report(current_user):
    """
    Export report as CSV
    ---
    tags:
      - Reports
    security:
      - Bearer: []
    parameters:
      - name: period
        in: query
        type: string
        default: monthly
      - name: format
        in: query
        type: string
        default: csv
    responses:
      200:
        description: CSV file download
    """
    period = request.args.get('period', 'monthly')
    format_type = request.args.get('format', 'csv')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    start, end = get_date_range(period, year, month)

    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= start,
        Expense.date <= end,
    ).all()

    if format_type == 'csv':
        def sanitize_csv_field(value):
            """Prevent CSV injection by prefixing formula characters."""
            if isinstance(value, str) and value and value[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
                return "'" + value
            return value

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Category', 'Amount', 'Payment Method', 'Merchant', 'Notes'])
        for e in expenses:
            writer.writerow([
                e.date.isoformat(),
                sanitize_csv_field(e.category.name if e.category else ''),
                float(e.amount),
                sanitize_csv_field(e.payment_method),
                sanitize_csv_field(e.merchant or ''),
                sanitize_csv_field(e.notes or ''),
            ])
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'expenses_{start}_{end}.csv'
        )

    return jsonify({'success': False, 'error': {'code': 'UNSUPPORTED', 'message': 'Only CSV export supported currently'}}), 400


@reports_api.route('/export-pdf', methods=['GET'])
@token_required
def export_pdf_report(current_user):
    """
    Export report as PDF
    ---
    tags:
      - Reports
    security:
      - Bearer: []
    parameters:
      - name: date_from
        in: query
        type: string
        required: true
        description: Start date (YYYY-MM-DD)
      - name: date_to
        in: query
        type: string
        required: true
        description: End date (YYYY-MM-DD)
    responses:
      200:
        description: PDF file download
      400:
        description: Invalid parameters
    """
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')

    if not date_from_str or not date_to_str:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION', 'message': 'date_from and date_to are required'}}), 400

    try:
        date_from = date.fromisoformat(date_from_str)
        date_to = date.fromisoformat(date_to_str)
    except ValueError:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION', 'message': 'Invalid date format. Use YYYY-MM-DD'}}), 400

    if date_from > date_to:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION', 'message': 'date_from must be before date_to'}}), 400

    # Fetch expenses in date range
    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= date_from,
        Expense.date <= date_to,
    ).order_by(Expense.date.asc()).all()

    # Fetch income in date range
    incomes = Income.query.filter(
        Income.user_id == current_user.id,
        Income.date >= date_from,
        Income.date <= date_to,
    ).order_by(Income.date.asc()).all()

    # Calculate totals
    total_expenses = sum(float(e.amount) for e in expenses)
    total_income = sum(float(i.amount) for i in incomes)
    net_savings = total_income - total_expenses
    savings_rate = round(net_savings / total_income * 100, 1) if total_income > 0 else 0

    # Category breakdown (expenses only)
    category_breakdown = db.session.query(
        Category.name.label('category_name'),
        func.sum(Expense.amount).label('total'),
        func.count(Expense.id).label('count')
    ).outerjoin(Category, Expense.category_id == Category.id).filter(
        Expense.user_id == current_user.id,
        Expense.date >= date_from,
        Expense.date <= date_to,
    ).group_by(Expense.category_id).all()

    category_list = []
    for cat in category_breakdown:
        cat_total = float(cat[1])
        category_list.append({
            'category_name': cat[0] or 'Uncategorized',
            'total': cat_total,
            'count': cat[2],
            'percentage': round(cat_total / total_expenses * 100, 1) if total_expenses > 0 else 0
        })

    # Build transactions list (income + expenses combined)
    transactions = []
    for inc in incomes:
        transactions.append({
            'date': inc.date.strftime('%d/%m/%Y'),
            'type': 'income',
            'category': inc.category.name if inc.category else (inc.source or 'Income'),
            'notes': inc.notes or inc.source or '-',
            'amount': float(inc.amount)
        })
    for exp in expenses:
        transactions.append({
            'date': exp.date.strftime('%d/%m/%Y'),
            'type': 'expense',
            'category': exp.category.name if exp.category else 'Uncategorized',
            'notes': exp.notes or exp.merchant or '-',
            'amount': float(exp.amount)
        })
    # Sort by date
    transactions.sort(key=lambda x: x['date'])

    # Payment method breakdown
    payment_methods_raw = db.session.query(
        Expense.payment_method,
        func.sum(Expense.amount).label('total'),
        func.count(Expense.id).label('count')
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= date_from,
        Expense.date <= date_to,
    ).group_by(Expense.payment_method).all()

    payment_methods = []
    for pm in payment_methods_raw:
        pm_total = float(pm[1])
        payment_methods.append({
            'method': pm[0] or 'Other',
            'total': pm_total,
            'count': pm[2],
            'percentage': round(pm_total / total_expenses * 100, 1) if total_expenses > 0 else 0
        })

    # Build report data
    report_data = {
        'date_from': date_from_str,
        'date_to': date_to_str,
        'user_name': current_user.name or current_user.email,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_savings': net_savings,
        'savings_rate': savings_rate,
        'income_count': len(incomes),
        'expense_count': len(expenses),
        'category_breakdown': category_list,
        'transactions': transactions,
        'payment_methods': payment_methods,
    }

    # Generate PDF
    pdf_bytes = generate_pdf_report(report_data)
    if pdf_bytes is None:
        return jsonify({'success': False, 'error': {'code': 'PDF_ERROR', 'message': 'Failed to generate PDF. Ensure reportlab is installed.'}}), 500

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'finance_report_{date_from_str}_to_{date_to_str}.pdf'
    )
