from datetime import datetime
from app.extensions import db


class SavingsPot(db.Model):
    __tablename__ = 'savings_pots'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    balance = db.Column(db.Numeric(12, 2), default=0)
    target_amount = db.Column(db.Numeric(12, 2), nullable=True)
    icon = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(7), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transactions = db.relationship('SavingsPotTransaction', backref='pot', lazy='dynamic', order_by='SavingsPotTransaction.date.desc()', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'balance': float(self.balance),
            'target_amount': float(self.target_amount) if self.target_amount is not None else None,
            'icon': self.icon,
            'color': self.color,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SavingsPotTransaction(db.Model):
    __tablename__ = 'savings_pot_transactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pot_id = db.Column(db.Integer, db.ForeignKey('savings_pots.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # deposit, withdrawal
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    account = db.relationship('Account', backref='pot_transactions')

    def to_dict(self):
        return {
            'id': self.id,
            'pot_id': self.pot_id,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'account_name': self.account.name if self.account else None,
            'amount': float(self.amount),
            'type': self.type,
            'date': self.date.isoformat(),
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
        }
