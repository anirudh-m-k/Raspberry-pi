import random
import string
from datetime import datetime
from decimal import Decimal
from sqlalchemy import func
from app.extensions import db
from app.models.event import Event
from app.models.event_member import EventMember
from app.models.event_category import EventCategory
from app.models.event_expense import EventExpense
from app.utils.constants import DEFAULT_EVENT_CATEGORIES


class EventService:
    @staticmethod
    def create_event_with_defaults(user_id, data, generate_join_code=False):
        """Atomic create: event + members + default categories + custom categories."""
        event = Event(
            user_id=user_id,
            name=data['name'],
            description=data.get('description'),
            start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data.get('start_date') else None,
            end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None,
            currency=data.get('currency', 'INR'),
            budget=Decimal(str(data['budget'])) if data.get('budget') else None,
            image_url=data.get('image_url'),
            status=data.get('status', 'planning'),
        )
        db.session.add(event)
        db.session.flush()  # get event.id

        # Add members from request
        members_data = data.get('members', [])
        for m in members_data:
            if m.get('name', '').strip():
                member = EventMember(
                    event_id=event.id,
                    name=m['name'].strip(),
                    nickname=m.get('nickname'),
                    color=m.get('color', '#6366f1'),
                    avatar=m.get('avatar'),
                    is_organizer=m.get('is_organizer', False),
                )
                db.session.add(member)

        # Seed default event categories
        for cat_data in DEFAULT_EVENT_CATEGORIES:
            cat = EventCategory(
                event_id=event.id,
                name=cat_data['name'],
                icon=cat_data['icon'],
                color=cat_data['color'],
            )
            db.session.add(cat)

        # Add any custom categories from request
        custom_cats = data.get('custom_categories', [])
        for cc in custom_cats:
            if cc.get('name', '').strip():
                cat = EventCategory(
                    event_id=event.id,
                    name=cc['name'].strip(),
                    icon=cc.get('icon'),
                    color=cc.get('color'),
                )
                db.session.add(cat)

        join_code_obj = None
        if generate_join_code:
            from app.models.event_join_code import EventJoinCode
            code = EventService._generate_unique_code()
            join_code_obj = EventJoinCode(
                event_id=event.id,
                code=code,
                created_by_user_id=user_id,
            )
            db.session.add(join_code_obj)

        db.session.commit()
        return event, join_code_obj

    @staticmethod
    def _generate_unique_code():
        """Generate unique 6-character alphanumeric join code."""
        from app.models.event_join_code import EventJoinCode
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not EventJoinCode.query.filter_by(code=code).first():
                return code

    @staticmethod
    def get_dashboard(event_id):
        """Aggregate queries for event dashboard."""
        from app.models.event_expense_split import EventExpenseSplit
        from app.models.event_member import EventMember
        from app.models.event_settlement import EventSettlement

        event = Event.query.get_or_404(event_id)

        # Total spent
        total_spent = db.session.query(func.sum(EventExpense.amount)) \
            .filter_by(event_id=event_id).scalar() or 0
        total_spent = float(total_spent)

        # Budget info
        budget = float(event.budget) if event.budget else None
        remaining = round(budget - total_spent, 2) if budget else None
        percent_used = round((total_spent / budget * 100), 1) if budget and budget > 0 else None

        # Member count
        member_count = EventMember.query.filter_by(event_id=event_id).count()

        # Avg per member
        avg_per_member = round(total_spent / member_count, 2) if member_count > 0 else 0

        # Category breakdown
        from app.models.event_category import EventCategory
        cat_breakdown = db.session.query(
            EventCategory.id,
            EventCategory.name,
            EventCategory.color,
            EventCategory.icon,
            func.sum(EventExpense.amount).label('total'),
            func.count(EventExpense.id).label('count')
        ).join(EventExpense, EventCategory.id == EventExpense.category_id) \
            .filter(EventExpense.event_id == event_id) \
            .group_by(EventCategory.id, EventCategory.name, EventCategory.color, EventCategory.icon) \
            .all()

        category_breakdown = [
            {
                'category_id': r.id,
                'name': r.name,
                'color': r.color,
                'icon': r.icon,
                'total': float(r.total),
                'count': r.count,
            }
            for r in cat_breakdown
        ]

        # Member spending (paid vs owed)
        members = EventMember.query.filter_by(event_id=event_id).all()
        member_spending = []
        for m in members:
            paid = db.session.query(func.sum(EventExpense.amount)) \
                .filter(EventExpense.paid_by_member_id == m.id,
                        EventExpense.event_id == event_id).scalar() or 0
            owed = db.session.query(func.sum(EventExpenseSplit.amount)) \
                .join(EventExpense, EventExpenseSplit.expense_id == EventExpense.id) \
                .filter(EventExpenseSplit.member_id == m.id,
                        EventExpense.event_id == event_id).scalar() or 0
            member_spending.append({
                'member_id': m.id,
                'name': m.name,
                'color': m.color,
                'paid': float(paid),
                'owed': float(owed),
                'net': round(float(paid) - float(owed), 2),
            })

        # Daily spending trend
        daily_rows = db.session.query(
            EventExpense.date,
            func.sum(EventExpense.amount).label('total'),
            func.count(EventExpense.id).label('count')
        ).filter_by(event_id=event_id) \
            .group_by(EventExpense.date) \
            .order_by(EventExpense.date).all()

        daily_spending = [
            {
                'date': r.date.isoformat(),
                'total': float(r.total),
                'count': r.count,
            }
            for r in daily_rows
        ]

        # Recent expenses (last 5)
        recent_expenses = EventExpense.query.filter_by(event_id=event_id) \
            .order_by(EventExpense.date.desc(), EventExpense.created_at.desc()) \
            .limit(5).all()

        # Pending settlements
        pending_settlements = EventSettlement.query.filter_by(
            event_id=event_id, is_completed=False
        ).count()

        # Budget warnings
        warnings = []
        if percent_used is not None:
            if percent_used >= 100:
                warnings.append('Budget exceeded!')
            elif percent_used >= 90:
                warnings.append('Budget at 90% — almost exhausted')
            elif percent_used >= 80:
                warnings.append('Budget at 80% — watch your spending')

        # Daily burn rate
        if daily_spending and budget:
            days_elapsed = len(daily_spending)
            daily_burn = round(total_spent / days_elapsed, 2) if days_elapsed > 0 else 0
        else:
            daily_burn = 0

        return {
            'summary': {
                'total_spent': round(total_spent, 2),
                'budget': budget,
                'remaining': remaining,
                'percent_used': percent_used,
                'member_count': member_count,
                'avg_per_member': avg_per_member,
                'expense_count': EventExpense.query.filter_by(event_id=event_id).count(),
                'pending_settlements': pending_settlements,
                'daily_burn_rate': daily_burn,
                'warnings': warnings,
            },
            'category_breakdown': category_breakdown,
            'member_spending': member_spending,
            'daily_spending': daily_spending,
            'recent_expenses': [e.to_short_dict() for e in recent_expenses],
        }

    @staticmethod
    def update_status_on_fetch(event):
        """Auto-transition status based on dates (in-memory only)."""
        today = datetime.utcnow().date()
        if event.status == 'planning' and event.start_date and event.start_date <= today:
            event.status = 'active'
        elif event.status == 'active' and event.end_date and event.end_date < today:
            event.status = 'completed'
        return event

    @staticmethod
    def generate_event_join_code(event_id, created_by_user_id, expires_at=None, max_uses=1):
        """Generate and persist a unique join code."""
        from app.models.event_join_code import EventJoinCode
        code = EventService._generate_unique_code()
        join_code = EventJoinCode(
            event_id=event_id,
            code=code,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
            max_uses=max_uses,
            current_uses=0,
        )
        db.session.add(join_code)
        db.session.commit()
        return join_code

    @staticmethod
    def join_event_by_code(code, joining_user_id):
        """Validate join code, add user to event_participation and auto-create an EventMember slot."""
        from app.models.event_join_code import EventJoinCode
        from app.models.event_participation import EventParticipation
        from app.models.user import User

        join_code = EventJoinCode.query.filter_by(code=code, is_active=True).first()
        if not join_code:
            return None, 'Invalid or inactive join code'

        now = datetime.utcnow()
        if join_code.expires_at and join_code.expires_at < now:
            return None, 'Join code has expired'

        if join_code.max_uses and join_code.current_uses >= join_code.max_uses:
            return None, 'Join code has reached maximum uses'

        event_id = join_code.event_id

        # Check if already participating
        existing = EventParticipation.query.filter_by(
            event_id=event_id,
            user_id=joining_user_id
        ).first()
        if existing:
            return join_code.event, 'Already participating in this event'

        # --- Add participation record ---
        participation = EventParticipation(
            event_id=event_id,
            user_id=joining_user_id,
            role='participant',
        )
        db.session.add(participation)

        # --- Auto-create EventMember slot if not already linked ---
        existing_member = EventMember.query.filter_by(
            event_id=event_id,
            linked_user_id=joining_user_id
        ).first()
        if not existing_member:
            joining_user = User.query.get(joining_user_id)
            member_name = joining_user.name if joining_user else 'Member'
            # Pick a distinct color from a palette
            palette = [
                '#6366f1', '#ec4899', '#f59e0b', '#10b981',
                '#3b82f6', '#8b5cf6', '#ef4444', '#14b8a6',
            ]
            # Use index of existing members count to pick a color
            existing_count = EventMember.query.filter_by(event_id=event_id).count()
            color = palette[existing_count % len(palette)]
            new_member = EventMember(
                event_id=event_id,
                name=member_name,
                color=color,
                is_organizer=False,
                linked_user_id=joining_user_id,
            )
            db.session.add(new_member)

        join_code.current_uses += 1
        if join_code.current_uses >= join_code.max_uses:
            join_code.is_active = False
        db.session.commit()
        return join_code.event, None

    @staticmethod
    def save_expense_receipt(user, event, expense, file_storage, serial_no=None):
        """
        Save uploaded receipt image/PDF under:
        app/static/uploads/events/[username]/[Event-name]/[serial.no].[date]-[Note].[ext]
        """
        import os
        import re
        from flask import current_app

        if not file_storage or not file_storage.filename:
            return None

        def sanitize_name(s):
            clean = re.sub(r'[^a-zA-Z0-9_\-]', '-', (s or '').strip())
            clean = re.sub(r'-+', '-', clean)
            return clean.strip('-') or 'default'

        raw_username = getattr(user, 'username', None) or getattr(user, 'name', None) or user.email.split('@')[0]
        username_dir = sanitize_name(raw_username)
        event_dir = sanitize_name(event.name)

        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'events', username_dir, event_dir)
        os.makedirs(upload_folder, exist_ok=True)

        ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else 'png'
        if ext not in ['png', 'jpg', 'jpeg', 'webp', 'pdf']:
            ext = 'png'

        if serial_no is None:
            serial_no = EventExpense.query.filter(
                EventExpense.event_id == event.id,
                EventExpense.id <= (expense.id or 999999)
            ).count() or 1

        date_str = expense.date.strftime('%b-%d') if expense.date else datetime.utcnow().strftime('%b-%d')
        raw_note = (expense.note or expense.merchant or (expense.category.name if expense.category else None) or 'Expense').strip()
        note_slug = sanitize_name(raw_note)[:30] or 'Expense'

        filename = f"{serial_no}.{date_str}-{note_slug}.{ext}"
        full_path = os.path.join(upload_folder, filename)

        file_storage.save(full_path)
        return f"/static/uploads/events/{username_dir}/{event_dir}/{filename}"

    @staticmethod
    def export_event_bills_zip(event_id):
        """Package all bill receipt files of an event into an in-memory ZIP buffer."""
        import os
        import io
        import zipfile
        import re
        from flask import current_app

        event = Event.query.get_or_404(event_id)
        expenses = EventExpense.query.filter_by(event_id=event_id) \
            .order_by(EventExpense.date.asc(), EventExpense.id.asc()).all()

        buffer = io.BytesIO()
        file_count = 0
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            idx = 1
            for exp in expenses:
                if exp.receipt_image:
                    rel_path = exp.receipt_image.lstrip('/')
                    disk_path = os.path.join(current_app.root_path, rel_path)
                    if os.path.exists(disk_path):
                        ext = disk_path.rsplit('.', 1)[-1].lower()
                        date_str = exp.date.strftime('%b-%d') if exp.date else 'Date'
                        raw_note = (exp.note or exp.merchant or 'Expense').strip()
                        clean_note = re.sub(r'[^a-zA-Z0-9_\-]', '-', raw_note)[:30] or 'Expense'
                        arc_name = f"{idx}.{date_str}-{clean_note}.{ext}"
                        zf.write(disk_path, arcname=arc_name)
                        idx += 1
                        file_count += 1

        buffer.seek(0)
        clean_event_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', event.name) or 'Event'
        zip_filename = f"{clean_event_name}_Bills.zip"
        return buffer, zip_filename, file_count


