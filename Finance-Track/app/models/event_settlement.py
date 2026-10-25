from datetime import datetime
from app.extensions import db


class EventSettlement(db.Model):
    __tablename__ = 'event_settlements'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    from_member_id = db.Column(db.Integer, db.ForeignKey('event_members.id'), nullable=False)
    to_member_id = db.Column(db.Integer, db.ForeignKey('event_members.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Two distinct FK relationships to EventMember
    from_member = db.relationship('EventMember', foreign_keys=[from_member_id])
    to_member = db.relationship('EventMember', foreign_keys=[to_member_id])

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'from_member_id': self.from_member_id,
            'from_member_name': self.from_member.name if self.from_member else None,
            'to_member_id': self.to_member_id,
            'to_member_name': self.to_member.name if self.to_member else None,
            'amount': float(self.amount),
            'is_completed': self.is_completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat(),
        }
