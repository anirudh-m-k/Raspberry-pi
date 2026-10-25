from datetime import datetime
from app.extensions import db


class Budget(db.Model):
    __tablename__ = 'budgets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)  # null = overall budget
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    period = db.Column(db.String(10), nullable=False)  # weekly, monthly
    month = db.Column(db.Integer, nullable=True)  # 1-12, for monthly
    year = db.Column(db.Integer, nullable=True)
    alert_threshold = db.Column(db.Integer, default=80)  # percentage
    is_active = db.Column(db.Boolean, default=True)
    auto_adjust = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = db.relationship('Category', backref='budgets')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'category_id', 'period', 'month', 'year', name='uq_user_budget'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else 'Overall',
            'amount': float(self.amount),
            'period': self.period,
            'month': self.month,
            'year': self.year,
            'alert_threshold': self.alert_threshold,
            'is_active': self.is_active,
            'auto_adjust': self.auto_adjust,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
