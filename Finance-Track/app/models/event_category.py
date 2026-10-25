from datetime import datetime
from app.extensions import db


class EventCategory(db.Model):
    __tablename__ = 'event_categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)  # null = global default
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(7), nullable=True)  # hex color
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    expenses = db.relationship('EventExpense', backref='category', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('event_id', 'name', name='uq_event_category_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'name': self.name,
            'icon': self.icon,
            'color': self.color,
            'created_at': self.created_at.isoformat(),
        }
