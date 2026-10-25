from datetime import datetime
from app.extensions import db


class OtpToken(db.Model):
    __tablename__ = 'otp_tokens'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(150), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    purpose = db.Column(db.String(20), nullable=False)  # verify, forgot
    name = db.Column(db.String(100), nullable=True)  # stored for registration
    password_hash = db.Column(db.String(255), nullable=True)  # stored for registration
    is_used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        return not self.is_used and self.expires_at > datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'purpose': self.purpose,
            'is_used': self.is_used,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat(),
        }
