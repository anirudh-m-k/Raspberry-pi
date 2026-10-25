from decimal import Decimal
from app.extensions import db
from app.models.event_expense_split import EventExpenseSplit


class SplitService:
    @staticmethod
    def calculate_equal_splits(total_amount, member_ids):
        """Equal split with remainder penny distribution.
        total=100.00, members=3 → [33.34, 33.33, 33.33]"""
        total = Decimal(str(total_amount))
        count = len(member_ids)
        if count == 0:
            return []
        per_member = (total / count).quantize(Decimal('0.01'), rounding='ROUND_DOWN')
        remainder = int((total - per_member * count) * 100)
        amounts = []
        for i in range(count):
            a = per_member + (Decimal('0.01') if i < remainder else Decimal('0'))
            amounts.append(float(a))
        return amounts

    @staticmethod
    def create_splits_for_expense(expense, split_data=None):
        """Create EventExpenseSplit records. Auto-generated for 'equal' type."""
        from app.models.event_member import EventMember
        members = EventMember.query.filter_by(event_id=expense.event_id).all()
        member_ids = [m.id for m in members]

        if not member_ids:
            return

        if expense.split_type == 'equal':
            if split_data:
                member_ids = [int(item.get('member_id')) for item in split_data]
                if not member_ids:
                    member_ids = [m.id for m in members]
            amounts = SplitService.calculate_equal_splits(expense.amount, member_ids)
            for mid, amt in zip(member_ids, amounts):
                split = EventExpenseSplit(
                    expense_id=expense.id,
                    member_id=mid,
                    amount=Decimal(str(amt))
                )
                db.session.add(split)

        elif expense.split_type in ('custom', 'percentage') and split_data:
            for item in split_data:
                mid = item.get('member_id')
                amt = item.get('amount', 0)
                pct = item.get('percentage')
                if mid and amt is not None:
                    split = EventExpenseSplit(
                        expense_id=expense.id,
                        member_id=mid,
                        amount=Decimal(str(amt)),
                        percentage=Decimal(str(pct)) if pct is not None else None
                    )
                    db.session.add(split)

    @staticmethod
    def delete_splits_for_expense(expense_id):
        """Delete all splits for an expense."""
        EventExpenseSplit.query.filter_by(expense_id=expense_id).delete()
        db.session.flush()
