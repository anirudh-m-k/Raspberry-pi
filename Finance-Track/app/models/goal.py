from datetime import datetime
from app.extensions import db


class Goal(db.Model):
    __tablename__ = 'goals'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_amount = db.Column(db.Numeric(12, 2), nullable=False)
    current_amount = db.Column(db.Numeric(12, 2), default=0)
    deadline = db.Column(db.Date, nullable=True)
    priority = db.Column(db.String(10), default='medium')  # low, medium, high
    image_url = db.Column(db.String(500), nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    auto_save_amount = db.Column(db.Numeric(12, 2), nullable=True)
    auto_save_frequency = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contributions = db.relationship('GoalContribution', backref='goal', lazy='dynamic', order_by='GoalContribution.date.desc()', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'target_amount': float(self.target_amount),
            'current_amount': float(self.current_amount),
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'priority': self.priority,
            'image_url': self.image_url,
            'is_completed': self.is_completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'auto_save_amount': float(self.auto_save_amount) if self.auto_save_amount else None,
            'auto_save_frequency': self.auto_save_frequency,
            'progress_percent': round((float(self.current_amount) / float(self.target_amount)) * 100, 1) if self.target_amount > 0 else 0,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class GoalContribution(db.Model):
    __tablename__ = 'goal_contributions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goals.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # manual, auto, withdrawal
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    account = db.relationship('Account', backref='goal_contributions')

    def to_dict(self):
        return {
            'id': self.id,
            'goal_id': self.goal_id,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'account_name': self.account.name if self.account else None,
            'amount': float(self.amount),
            'type': self.type,
            'date': self.date.isoformat(),
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
        }
