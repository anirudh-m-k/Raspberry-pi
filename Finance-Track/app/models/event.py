from datetime import datetime
from app.extensions import db
from app.models.event_member import EventMember
from app.models.event_category import EventCategory
from app.models.event_expense import EventExpense
from app.models.event_expense_split import EventExpenseSplit
from app.models.event_settlement import EventSettlement


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    currency = db.Column(db.String(3), default='INR')
    budget = db.Column(db.Numeric(12, 2), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='planning')  # planning, active, completed, archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='created_events')
    members = db.relationship('EventMember', backref='event', lazy='dynamic',
                              cascade='all, delete-orphan')
    categories = db.relationship('EventCategory', backref='event', lazy='dynamic',
                                 cascade='all, delete-orphan')
    expenses = db.relationship('EventExpense', backref='event', lazy='dynamic',
                               cascade='all, delete-orphan')
    settlements = db.relationship('EventSettlement', backref='event', lazy='dynamic',
                                  cascade='all, delete-orphan')
    join_codes = db.relationship('EventJoinCode', back_populates='event', lazy='dynamic',
                                 cascade='all, delete-orphan',
                                 foreign_keys='EventJoinCode.event_id')
    participations = db.relationship('EventParticipation', back_populates='event', lazy='dynamic',
                                     cascade='all, delete-orphan',
                                     foreign_keys='EventParticipation.event_id')

    __table_args__ = (
        db.Index('ix_events_user_status', 'user_id', 'status'),
    )

    def _calc_total_spent(self):
        from sqlalchemy import func
        result = db.session.query(func.sum(EventExpense.amount)).filter(
            EventExpense.event_id == self.id
        ).scalar()
        return float(result) if result else 0.0

    def to_dict(self):
        from app.models.event_join_code import EventJoinCode
        active_code = EventJoinCode.query.filter_by(event_id=self.id, is_active=True).order_by(EventJoinCode.created_at.desc()).first()
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'currency': self.currency,
            'budget': float(self.budget) if self.budget else None,
            'image_url': self.image_url,
            'status': self.status,
            'member_count': self.members.count(),
            'expense_count': self.expenses.count(),
            'total_spent': self._calc_total_spent(),
            'join_code': active_code.code if active_code else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
