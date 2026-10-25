from datetime import datetime
from app.extensions import db


class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=True)
    payment_method = db.Column(db.String(30), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    merchant = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_recurring_generated = db.Column(db.Boolean, default=False)
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_transactions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = db.relationship('Category', foreign_keys=[category_id], backref='expenses')
    subcategory = db.relationship('Category', foreign_keys=[subcategory_id], backref='sub_expenses')
    recurring = db.relationship('RecurringTransaction', backref='generated_expenses')

    __table_args__ = (
        db.Index('ix_expenses_user_date', 'user_id', 'date'),
        db.Index('ix_expenses_user_category', 'user_id', 'category_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount),
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'subcategory_id': self.subcategory_id,
            'subcategory_name': self.subcategory.name if self.subcategory else None,
            'date': self.date.isoformat(),
            'time': self.time.isoformat() if self.time else None,
            'payment_method': self.payment_method,
            'account_id': self.account_id,
            'account_name': self.account.name if self.account else None,
            'merchant': self.merchant,
            'notes': self.notes,
            'is_recurring_generated': self.is_recurring_generated,
            'recurring_id': self.recurring_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
