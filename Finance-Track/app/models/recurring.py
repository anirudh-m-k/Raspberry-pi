from datetime import datetime
from app.extensions import db


class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # expense, income
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly, quarterly, yearly
    payment_method = db.Column(db.String(30), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    next_due_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_paused = db.Column(db.Boolean, default=False)
    auto_add = db.Column(db.Boolean, default=True)
    reminder_days_before = db.Column(db.Integer, default=3)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = db.relationship('Category', backref='recurring_transactions')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'amount': float(self.amount),
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'frequency': self.frequency,
            'payment_method': self.payment_method,
            'account_id': self.account_id,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'next_due_date': self.next_due_date.isoformat(),
            'is_active': self.is_active,
            'is_paused': self.is_paused,
            'auto_add': self.auto_add,
            'reminder_days_before': self.reminder_days_before,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
