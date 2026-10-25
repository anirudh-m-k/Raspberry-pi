import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    username = db.Column(db.String(50), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    avatar_url = db.Column(db.String(500), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    expenses = db.relationship('Expense', backref='user', lazy='dynamic')
    incomes = db.relationship('Income', backref='user', lazy='dynamic')
    recurring_transactions = db.relationship('RecurringTransaction', backref='user', lazy='dynamic')
    budgets = db.relationship('Budget', backref='user', lazy='dynamic')
    goals = db.relationship('Goal', backref='user', lazy='dynamic')
    savings_pots = db.relationship('SavingsPot', backref='user', lazy='dynamic')
    accounts = db.relationship('Account', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    settings = db.relationship('Setting', backref='user', uselist=False)
    categories = db.relationship('Category', backref='user', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return self.id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'username': self.username,
            'role': self.role,
            'is_verified': self.is_verified,
            'is_active': self.is_active,
            'avatar_url': self.avatar_url,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
        }
