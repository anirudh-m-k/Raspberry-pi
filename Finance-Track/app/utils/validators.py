import re


def validate_email(email):
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(password):
    """Check password strength. Returns (is_valid, message)."""
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one digit'
    return True, 'Password is strong'


def validate_amount(amount):
    """Validate that amount is a positive number."""
    try:
        val = float(amount)
        return val > 0
    except (ValueError, TypeError):
        return False
