from datetime import datetime
from app.extensions import db


class EventJoinCode(db.Model):
    __tablename__ = 'event_join_codes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    code = db.Column(db.String(6), unique=True, nullable=False)  # 6 char unique code
    is_active = db.Column(db.Boolean, default=True)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    max_uses = db.Column(db.Integer, default=1)
    current_uses = db.Column(db.Integer, default=0)

    # Relationships — event side uses cascade='all, delete-orphan' on Event.join_codes
    event = db.relationship('Event', back_populates='join_codes',
                            foreign_keys=[event_id])
    creator = db.relationship('User', backref=db.backref('created_join_codes', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'code': self.code,
            'is_active': self.is_active,
            'created_by_user_id': self.created_by_user_id,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'max_uses': self.max_uses,
            'current_uses': self.current_uses,
        }
