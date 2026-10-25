import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.setting import Setting


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    app = create_app('testing')
    return app


@pytest.fixture(scope='function')
def db(app):
    """Create database tables for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers(app, db):
    """Create authenticated user and return auth headers."""
    with app.app_context():
        user = User(name='Test User', email='test@example.com')
        user.set_password('TestPass123')
        user.is_verified = True
        _db.session.add(user)
        _db.session.flush()

        settings = Setting(user_id=user.id)
        _db.session.add(settings)
        _db.session.commit()

        from app.utils.decorators import generate_token
        token = generate_token(user)

        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }, user.id
