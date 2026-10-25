from flask import request
from app.extensions import db
from app.models.audit_log import AuditLog


def log_audit(user_id, action, entity_type=None, entity_id=None, details=None):
    """Create an audit log entry for sensitive operations."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        details=details,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(log)
    db.session.commit()
    return log
