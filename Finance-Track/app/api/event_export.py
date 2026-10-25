import io
import csv
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from app.models.event import Event
from app.models.event_expense import EventExpense
from app.models.event_category import EventCategory
from app.models.event_member import EventMember
from app.utils.decorators import token_required

event_export_api = Blueprint('event_export_api', __name__)


def check_event_ownership(event_id, current_user):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return None, jsonify({'success': False, 'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}}), 403
    return event, None, None


@event_export_api.route('', methods=['GET'])
@token_required
def export_event(current_user, event_id):
    """Export event expenses as CSV, XLSX, or PDF."""
    event, err, code = check_event_ownership(event_id, current_user)
    if err:
        return err, code

    fmt = request.args.get('format', 'csv').lower()
    expenses = EventExpense.query.filter_by(event_id=event_id) \
        .order_by(EventExpense.date.asc()).all()

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Category', 'Paid By', 'Amount', 'Note', 'Merchant', 'Split Type'])
        for e in expenses:
            writer.writerow([
                e.date.isoformat(),
                e.category.name if e.category else '',
                e.payer.name if e.payer else '',
                float(e.amount),
                e.note or '',
                e.merchant or '',
                e.split_type,
            ])
        output.seek(0)
        filename = f"event_{event_id}_{event.name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    elif fmt == 'xlsx':
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Event Expenses'
            headers = ['Date', 'Category', 'Paid By', 'Amount', 'Note', 'Merchant', 'Split Type']
            ws.append(headers)
            for e in expenses:
                ws.append([
                    e.date.isoformat(),
                    e.category.name if e.category else '',
                    e.payer.name if e.payer else '',
                    float(e.amount),
                    e.note or '',
                    e.merchant or '',
                    e.split_type,
                ])
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            filename = f"event_{event_id}_{event.name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        except ImportError:
            return jsonify({'success': False, 'error': {'code': 'NOT_SUPPORTED', 'message': 'openpyxl not installed'}}), 500

    elif fmt == 'pdf':
        # Generate simple PDF summary
        try:
            from app.services.export_service import generate_event_pdf
            pdf_bytes = generate_event_pdf(event, expenses)
            filename = f"event_{event_id}_{event.name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            return jsonify({'success': False, 'error': {'code': 'EXPORT_ERROR', 'message': str(e)}}), 500

    else:
        return jsonify({'success': False, 'error': {'code': 'INVALID_FORMAT', 'message': 'format must be csv, xlsx, or pdf'}}), 400
