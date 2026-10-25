from datetime import datetime
from app.extensions import db


class ReportsCache(db.Model):
    __tablename__ = 'reports_cache'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    report_type = db.Column(db.String(30), nullable=False)
    period_key = db.Column(db.String(50), nullable=False)
    data = db.Column(db.Text, nullable=False)  # JSON blob
    generated_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'report_type', 'period_key', name='uq_user_report'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'report_type': self.report_type,
            'period_key': self.period_key,
            'data': self.data,
            'generated_at': self.generated_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }
