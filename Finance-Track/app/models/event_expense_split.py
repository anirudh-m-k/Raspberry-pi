from datetime import datetime
from app.extensions import db


class EventExpenseSplit(db.Model):
    __tablename__ = 'event_expense_splits'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('event_expenses.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('event_members.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    percentage = db.Column(db.Numeric(5, 2), nullable=True)
    is_settled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('expense_id', 'member_id', name='uq_expense_member_split'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'expense_id': self.expense_id,
            'member_id': self.member_id,
            'member_name': self.member.name if self.member else None,
            'member_color': self.member.color if self.member else None,
            'amount': float(self.amount),
            'percentage': float(self.percentage) if self.percentage else None,
            'is_settled': self.is_settled,
            'created_at': self.created_at.isoformat(),
        }
