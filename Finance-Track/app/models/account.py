from datetime import datetime
from app.extensions import db


class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # cash, bank, credit_card, upi, wallet, investment
    balance = db.Column(db.Numeric(12, 2), default=0)
    currency = db.Column(db.String(3), default='INR')
    institution = db.Column(db.String(100), nullable=True)
    account_number = db.Column(db.String(50), nullable=True)  # encrypted
    is_active = db.Column(db.Boolean, default=True)
    is_hidden = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    expenses = db.relationship('Expense', backref='account', lazy='dynamic')
    incomes = db.relationship('Income', backref='account', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'type': self.type,
            'balance': float(self.balance),
            'currency': self.currency,
            'institution': self.institution,
            'is_active': self.is_active,
            'is_hidden': self.is_hidden,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
