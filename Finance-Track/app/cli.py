"""CLI commands for FinanceTrack."""
import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models.user import User
from app.models.category import Category
from app.models.setting import Setting
from app.utils.constants import DEFAULT_EXPENSE_CATEGORIES, DEFAULT_INCOME_CATEGORIES, DEFAULT_RECURRING_CATEGORIES


def seed_default_categories():
    """Seed default categories if none exist. Called automatically on startup."""
    existing = Category.query.filter_by(is_default=True).count()
    if existing > 0:
        return

    count = 0

    for cat_data in DEFAULT_EXPENSE_CATEGORIES:
        cat = Category(
            name=cat_data['name'],
            type='expense',
            icon=cat_data.get('icon'),
            color=cat_data.get('color'),
            is_default=True,
        )
        db.session.add(cat)
        count += 1

    for cat_data in DEFAULT_INCOME_CATEGORIES:
        cat = Category(
            name=cat_data['name'],
            type='income',
            icon=cat_data.get('icon'),
            color=cat_data.get('color'),
            is_default=True,
        )
        db.session.add(cat)
        count += 1

    for cat_data in DEFAULT_RECURRING_CATEGORIES:
        cat = Category(
            name=cat_data['name'],
            type='recurring',
            icon=cat_data.get('icon'),
            color=cat_data.get('color'),
            is_default=True,
        )
        db.session.add(cat)
        count += 1

    db.session.commit()


@click.command('seed-categories')
@with_appcontext
def seed_categories():
    """Seed default categories for expenses, income, and recurring."""
    seed_default_categories()
    click.echo('Default categories seeded.')


@click.command('create-user')
@click.option('--name', prompt='Name', help='User name')
@click.option('--email', prompt='Email', help='User email')
@click.option('--password', prompt='Password', hide_input=True, confirmation_prompt=True, help='User password')
@with_appcontext
def create_user(name, email, password):
    """Create a new user."""
    if User.query.filter_by(email=email.lower()).first():
        click.echo(f'User with email {email} already exists.')
        return

    # First user becomes admin
    is_first = User.query.count() == 0
    role = 'admin' if is_first else 'user'

    user = User(name=name, email=email.lower(), is_verified=True, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    settings = Setting(user_id=user.id)
    db.session.add(settings)
    db.session.commit()

    click.echo(f'User created: {user.name} ({user.email}) - Role: {user.role}')
    click.echo(f'User ID: {user.id}')


@click.command('seed-all')
@with_appcontext
def seed_all():
    """Seed all default data (categories + demo user)."""
    seed_default_categories()

    demo_email = 'demo@financetrack.com'
    if not User.query.filter_by(email=demo_email).first():
        user = User(name='Demo User', email=demo_email, is_verified=True, role='admin')
        user.set_password('Demo@123')
        db.session.add(user)
        db.session.flush()

        settings = Setting(user_id=user.id)
        db.session.add(settings)
        db.session.commit()

        click.echo(f'Demo admin created: {user.name} ({user.email})')
        click.echo(f'Password: Demo@123')
    else:
        click.echo('Demo user already exists.')


def register_commands(app):
    """Register CLI commands."""
    app.cli.add_command(seed_categories)
    app.cli.add_command(create_user)
    app.cli.add_command(seed_all)
