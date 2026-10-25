from datetime import datetime
from app.extensions import db


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, unique=True)
    currency = db.Column(db.String(3), default='INR')
    timezone = db.Column(db.String(50), default='Asia/Kolkata')
    theme = db.Column(db.String(10), default='dark')  # light, dark, system
    date_format = db.Column(db.String(20), default='DD/MM/YYYY')
    month_start_day = db.Column(db.Integer, default=1)
    session_timeout_minutes = db.Column(db.Integer, default=60)
    notification_email = db.Column(db.Boolean, default=True)
    notification_browser = db.Column(db.Boolean, default=True)
    backup_frequency = db.Column(db.String(20), default='weekly')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'currency': self.currency,
            'timezone': self.timezone,
            'theme': self.theme,
            'date_format': self.date_format,
            'month_start_day': self.month_start_day,
            'session_timeout_minutes': self.session_timeout_minutes,
            'notification_email': self.notification_email,
            'notification_browser': self.notification_browser,
            'backup_frequency': self.backup_frequency,
        }
