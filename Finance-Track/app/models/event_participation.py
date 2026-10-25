from datetime import datetime
from app.extensions import db


class EventParticipation(db.Model):
    __tablename__ = 'event_participation'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='participant')  # 'participant', 'admin', 'viewer'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships — event side uses cascade='all, delete-orphan' on Event.participations
    event = db.relationship('Event', back_populates='participations',
                            foreign_keys=[event_id])
    user = db.relationship('User', backref=db.backref('event_participations', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'user_id': self.user_id,
            'role': self.role,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'created_at': self.created_at.isoformat(),
        }
