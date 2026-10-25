from datetime import datetime
from app.extensions import db


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)  # null = system default
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # expense, income, recurring_expense, recurring_income
    icon = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(7), nullable=True)  # hex color
    is_default = db.Column(db.Boolean, default=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    subcategories = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', 'type', 'parent_id', name='uq_user_category'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'type': self.type,
            'icon': self.icon,
            'color': self.color,
            'is_default': self.is_default,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat(),
        }
