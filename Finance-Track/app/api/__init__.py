from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


def register_api(app):
    """Register all API endpoints."""
    from app.api.auth import auth_api
    from app.api.expenses import expenses_api
    from app.api.income import income_api
    from app.api.accounts import accounts_api
    from app.api.recurring import recurring_api
    from app.api.budgets import budgets_api
    from app.api.goals import goals_api
    from app.api.savings_pots import savings_pots_api
    from app.api.dashboard import dashboard_api
    from app.api.reports import reports_api
    from app.api.calendar import calendar_api
    from app.api.notifications import notifications_api
    from app.api.settings import settings_api
    from app.api.admin.routes import admin_api
    from app.api.events import events_api
    from app.api.event_members import event_members_api
    from app.api.event_categories import event_categories_api
    from app.api.event_expenses import event_expenses_api
    from app.api.event_dashboard import event_dashboard_api
    from app.api.event_settlements import event_settlements_api
    from app.api.event_export import event_export_api

    api_bp.register_blueprint(auth_api, url_prefix='/auth')
    api_bp.register_blueprint(expenses_api, url_prefix='/expenses')
    api_bp.register_blueprint(income_api, url_prefix='/income')
    api_bp.register_blueprint(accounts_api, url_prefix='/accounts')
    api_bp.register_blueprint(recurring_api, url_prefix='/recurring')
    api_bp.register_blueprint(budgets_api, url_prefix='/budgets')
    api_bp.register_blueprint(goals_api, url_prefix='/goals')
    api_bp.register_blueprint(savings_pots_api, url_prefix='/savings-pots')
    api_bp.register_blueprint(dashboard_api, url_prefix='/dashboard')
    api_bp.register_blueprint(reports_api, url_prefix='/reports')
    api_bp.register_blueprint(calendar_api, url_prefix='/calendar')
    api_bp.register_blueprint(notifications_api, url_prefix='/notifications')
    api_bp.register_blueprint(settings_api, url_prefix='/settings')
    api_bp.register_blueprint(admin_api, url_prefix='/admin')

    # Event module blueprints
    api_bp.register_blueprint(events_api, url_prefix='/events')
    events_api.register_blueprint(event_members_api, url_prefix='/<int:event_id>/members')
    events_api.register_blueprint(event_categories_api, url_prefix='/<int:event_id>/categories')
    events_api.register_blueprint(event_expenses_api, url_prefix='/<int:event_id>/expenses')
    events_api.register_blueprint(event_dashboard_api, url_prefix='/<int:event_id>/dashboard')
    events_api.register_blueprint(event_settlements_api, url_prefix='/<int:event_id>/settlements')
    events_api.register_blueprint(event_export_api, url_prefix='/<int:event_id>/export')

    app.register_blueprint(api_bp)

