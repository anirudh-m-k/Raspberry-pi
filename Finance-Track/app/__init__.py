import os
from flask import Flask, jsonify, redirect
from flasgger import Swagger
from flask_migrate import Migrate
from app.config import config
from app.extensions import db, login_manager, csrf, mail, limiter, talisman, scheduler


def create_app(config_name='development'):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    # CSRF disabled - API uses JWT auth (Bearer tokens), not cookie-based sessions
    app.config['WTF_CSRF_ENABLED'] = False
    mail.init_app(app)
    limiter.init_app(app)
    migrate = Migrate(app, db)

    # Configure Swagger UI
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/api/spec",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs",
    }
    swagger_template = {
        "info": {
            "title": "FinanceTrack API",
            "description": "REST API for FinanceTrack personal finance management application",
            "version": "1.0.0",
            "contact": {
                "name": "FinanceTrack Support",
                "email": "support@financetrack.com",
            },
        },
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "Enter 'Bearer {token}' to authenticate",
            }
        },
        "security": [{"Bearer": []}],
    }
    Swagger(app, config=swagger_config, template=swagger_template)

    # Talisman with relaxed settings for dev
    if config_name == 'production':
        talisman.init_app(app, force_https=True)
    else:
        talisman.init_app(app, force_https=False, content_security_policy=False)

    # Configure login manager
    login_manager.login_view = 'pages.login'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(user_id)

    # Register API blueprint
    from app.api import register_api
    register_api(app)

    # Register page-serving blueprint
    from app.blueprints.pages import pages_bp
    app.register_blueprint(pages_bp)

    # Register Jinja2 filters
    from app.utils.filters import register_filters
    register_filters(app)

    # Register error handlers
    register_error_handlers(app)

    # Register CLI commands
    from app.cli import register_commands
    register_commands(app)

    # Initialize scheduler
    init_scheduler(app)

    # Auto-create DB tables and seed default data
    with app.app_context():
        from app.services.backup_service import ensure_db_schema
        ensure_db_schema()
        from app.cli import seed_default_categories
        seed_default_categories()

    return app


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        from flask import request
        if request.accept_mimetypes.accept_html:
            return app.jinja_env.get_template('errors/404.html').render(), 404
        return jsonify({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'The requested resource was not found'
            }
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import request
        if request.accept_mimetypes.accept_html:
            return app.jinja_env.get_template('errors/500.html').render(), 500
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }), 500

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'success': False,
            'error': {
                'code': 'UNAUTHORIZED',
                'message': 'Authentication required'
            }
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'success': False,
            'error': {
                'code': 'FORBIDDEN',
                'message': 'You do not have permission to access this resource'
            }
        }), 403

    @app.errorhandler(429)
    def ratelimit_handler(error):
        return jsonify({
            'success': False,
            'error': {
                'code': 'RATE_LIMIT_EXCEEDED',
                'message': 'Too many requests. Please try again later.'
            }
        }), 429


def init_scheduler(app):
    """Initialize APScheduler jobs."""
    from app.services.scheduler_jobs import (
        process_recurring_transactions,
        send_recurring_reminders,
        check_budget_alerts,
        generate_weekly_summary,
        generate_monthly_summary,
    )
    from apscheduler.triggers.cron import CronTrigger

    with app.app_context():
        scheduler.add_job(
            func=process_recurring_transactions,
            trigger=CronTrigger(hour=0, minute=0),
            id='process_recurring',
            replace_existing=True,
            args=[app],
        )
        scheduler.add_job(
            func=send_recurring_reminders,
            trigger=CronTrigger(hour=8, minute=0),
            id='send_reminders',
            replace_existing=True,
            args=[app],
        )
        scheduler.add_job(
            func=check_budget_alerts,
            trigger=CronTrigger(hour=21, minute=0),
            id='check_budgets',
            replace_existing=True,
            args=[app],
        )
        scheduler.add_job(
            func=generate_weekly_summary,
            trigger=CronTrigger(day_of_week='mon', hour=7, minute=0),
            id='weekly_summary',
            replace_existing=True,
            args=[app],
        )
        scheduler.add_job(
            func=generate_monthly_summary,
            trigger=CronTrigger(day=1, hour=7, minute=0),
            id='monthly_summary',
            replace_existing=True,
            args=[app],
        )

        try:
            scheduler.start()
        except Exception:
            pass  # Scheduler already running
