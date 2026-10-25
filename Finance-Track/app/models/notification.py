from datetime import datetime
from app.extensions import db


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), nullable=False)  # emi_due, subscription_renew, budget_exceeded, etc.
    is_read = db.Column(db.Boolean, default=False)
    related_entity_type = db.Column(db.String(30), nullable=True)  # expense, income, budget, goal, recurring
    related_entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_notifications_user_read', 'user_id', 'is_read', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id,
            'created_at': self.created_at.isoformat(),
        }
