import os
from datetime import timedelta


def _get_secret(name, fallback='dev-secret'):
    """Get secret from env, fail loudly in production if using default."""
    value = os.environ.get(name)
    if not value or value.startswith('dev-'):
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError(f"{name} environment variable is required in production and must not be a default value")
        if not value:
            value = fallback
    return value


class Config:
    SECRET_KEY = _get_secret('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///finance_track.db')

    # JWT
    JWT_SECRET_KEY = _get_secret('JWT_SECRET_KEY', 'dev-jwt-secret')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 1025))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@financetrack.com')

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)

    # Rate limiting
    RATELIMIT_DEFAULT = "200 per hour"
    RATELIMIT_STORAGE_URI = "memory://"


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///finance_track.db')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
