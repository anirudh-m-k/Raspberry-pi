from datetime import datetime, date


def register_filters(app):
    @app.template_filter('currency')
    def currency_filter(amount, symbol='₹'):
        try:
            return f"{symbol}{float(amount):,.2f}"
        except (ValueError, TypeError):
            return f"{symbol}0.00"

    @app.template_filter('dateformat')
    def dateformat(value, fmt='%d/%m/%Y'):
        if isinstance(value, (datetime, date)):
            return value.strftime(fmt)
        return value

    @app.template_filter('timeformat')
    def timeformat(value, fmt='%I:%M %p'):
        if isinstance(value, datetime):
            return value.strftime(fmt)
        return value

    @app.template_filter('timeago')
    def timeago(value):
        if not isinstance(value, datetime):
            return value
        now = datetime.utcnow()
        diff = now - value
        seconds = diff.total_seconds()
        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes}m ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours}h ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days}d ago'
        else:
            return value.strftime('%d %b %Y')
