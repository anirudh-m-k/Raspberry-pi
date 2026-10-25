from datetime import datetime
from app.extensions import db


class EventExpense(db.Model):
    __tablename__ = 'event_expenses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('event_categories.id'), nullable=True)
    paid_by_member_id = db.Column(db.Integer, db.ForeignKey('event_members.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    note = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    merchant = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    receipt_image = db.Column(db.String(500), nullable=True)
    tags = db.Column(db.String(500), nullable=True)
    split_type = db.Column(db.String(20), default='equal')  # equal, custom, percentage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    splits = db.relationship('EventExpenseSplit', backref='expense', lazy='dynamic',
                             cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('ix_event_expenses_date', 'event_id', 'date'),
        db.Index('ix_event_expenses_category', 'event_id', 'category_id'),
        db.Index('ix_event_expenses_payer', 'event_id', 'paid_by_member_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'amount': float(self.amount),
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else 'Uncategorized',
            'category_color': self.category.color if self.category else '#94a3b8',
            'category_icon': self.category.icon if self.category else None,
            'category': {
                'id': self.category.id,
                'name': self.category.name,
                'color': self.category.color or '#94a3b8'
            } if self.category else {'id': None, 'name': 'Uncategorized', 'color': '#94a3b8'},
            'paid_by_member_id': self.paid_by_member_id,
            'paid_by_name': self.payer.name if self.payer else 'Member',
            'paid_by_color': self.payer.color if self.payer else '#6366f1',
            'paid_by': {
                'id': self.payer.id,
                'name': self.payer.name,
                'color': self.payer.color or '#6366f1'
            } if self.payer else {'id': None, 'name': 'Member', 'color': '#6366f1'},
            'date': self.date.isoformat(),
            'note': self.note,
            'description': self.description,
            'merchant': self.merchant,
            'location': self.location,
            'receipt_image': self.receipt_image,
            'tags': self.tags.split(',') if self.tags else [],
            'split_type': self.split_type,
            'splits': [s.to_dict() for s in self.splits.all()],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_short_dict(self):
        """Lightweight version without splits for list views."""
        return {
            'id': self.id,
            'event_id': self.event_id,
            'amount': float(self.amount),
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else 'Uncategorized',
            'category_color': self.category.color if self.category else '#94a3b8',
            'category_icon': self.category.icon if self.category else None,
            'category': {
                'id': self.category.id,
                'name': self.category.name,
                'color': self.category.color or '#94a3b8'
            } if self.category else {'id': None, 'name': 'Uncategorized', 'color': '#94a3b8'},
            'paid_by_member_id': self.paid_by_member_id,
            'paid_by_name': self.payer.name if self.payer else 'Member',
            'paid_by_color': self.payer.color if self.payer else '#6366f1',
            'paid_by': {
                'id': self.payer.id,
                'name': self.payer.name,
                'color': self.payer.color or '#6366f1'
            } if self.payer else {'id': None, 'name': 'Member', 'color': '#6366f1'},
            'date': self.date.isoformat(),
            'note': self.note,
            'description': self.description,
            'merchant': self.merchant,
            'receipt_image': self.receipt_image,
            'split_type': self.split_type,
            'created_at': self.created_at.isoformat(),
        }
