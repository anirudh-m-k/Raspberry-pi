from datetime import datetime
from app.extensions import db


class EventMember(db.Model):
    __tablename__ = 'event_members'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(100), nullable=True)
    color = db.Column(db.String(7), nullable=True)
    avatar = db.Column(db.String(10), nullable=True)
    is_organizer = db.Column(db.Boolean, default=False)
    # Nullable FK — set when a registered user joins via invite code
    linked_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    paid_expenses = db.relationship('EventExpense', foreign_keys='EventExpense.paid_by_member_id',
                                    backref='payer', lazy='dynamic')
    splits = db.relationship('EventExpenseSplit', backref='member', lazy='dynamic')
    linked_user = db.relationship('User', backref=db.backref('event_member_slots', lazy='dynamic'),
                                  foreign_keys=[linked_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'name': self.name,
            'nickname': self.nickname,
            'color': self.color,
            'avatar': self.avatar,
            'is_organizer': self.is_organizer,
            'linked_user_id': self.linked_user_id,
            'created_at': self.created_at.isoformat(),
        }

