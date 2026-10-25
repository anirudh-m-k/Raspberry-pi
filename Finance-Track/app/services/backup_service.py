"""Database backup and restore service."""
import os
import shutil
from datetime import datetime
from flask import current_app
from app.extensions import db


def get_db_path():
    """Get the absolute path to the SQLite database file."""
    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    db_path = db_uri.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_app.instance_path, db_path)
    return db_path


def create_backup():
    """Create a backup of the SQLite database. Returns backup file path or None."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None

    backup_dir = os.path.join(current_app.instance_path, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'finance_track_backup_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)

    # Use SQLite backup API for safe hot backup
    import sqlite3
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        src.backup(dst)
        dst.close()
        src.close()
    except Exception:
        # Fallback to file copy
        shutil.copy2(db_path, backup_path)

    return backup_path


def ensure_db_schema():
    """Ensure all required tables and columns exist in the database after startup or backup restore."""
    from app.extensions import db
    from app.models import (
        User, Category, Account, Expense, Income, RecurringTransaction,
        Budget, Goal, GoalContribution, SavingsPot, SavingsPotTransaction,
        Notification, Setting, AuditLog, ReportsCache, EventCategory,
        EventMember, EventExpenseSplit, EventSettlement, EventExpense,
        Event, EventParticipation, EventJoinCode
    )
    from sqlalchemy import text, inspect

    # 1. Create any missing tables (e.g. events, event_members, etc.)
    db.create_all()

    # 2. Check & add missing columns on existing tables for old backup compatibility
    try:
        inspector = inspect(db.engine)
        if 'event_members' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('event_members')]
            if 'linked_user_id' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE event_members ADD COLUMN linked_user_id VARCHAR(36) REFERENCES users(id)'))
                    conn.commit()

        if 'event_expenses' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('event_expenses')]
            if 'description' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE event_expenses ADD COLUMN description TEXT'))
                    conn.commit()

        if 'savings_pots' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('savings_pots')]
            if 'target_amount' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE savings_pots ADD COLUMN target_amount NUMERIC(12, 2)'))
                    conn.commit()
    except Exception as e:
        print(f'Warning during schema migration: {e}')


def restore_backup(uploaded_file_path):
    """Restore database from an uploaded backup file.

    Validates the file is a valid SQLite database with the expected schema,
    creates a safety backup of the current DB, replaces it, and migrates missing tables/columns.

    Args:
        uploaded_file_path: Path to the uploaded .db file

    Returns:
        tuple: (success: bool, message: str)
    """
    db_path = get_db_path()

    # Validate the uploaded file is a valid SQLite database
    import sqlite3
    try:
        conn = sqlite3.connect(uploaded_file_path)
        cursor = conn.cursor()

        # Check it's a valid SQLite file
        cursor.execute("SELECT count(*) FROM sqlite_master")
        table_count = cursor.fetchone()[0]
        if table_count == 0:
            conn.close()
            return False, "Invalid database file: no tables found"

        # Check for expected tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        required_tables = ['users']
        missing = [t for t in required_tables if t not in tables]
        if missing:
            return False, f"Invalid backup: missing required tables: {', '.join(missing)}"

    except sqlite3.DatabaseError:
        return False, "File is not a valid SQLite database"
    except Exception as e:
        return False, f"Error validating database: {str(e)}"

    # Create safety backup of current database
    safety_backup = create_backup()
    if safety_backup:
        current_app.logger.info(f"Safety backup created at: {safety_backup}")

    # Close all existing connections
    db.engine.dispose()

    # Replace the current database with the backup
    try:
        shutil.copy2(uploaded_file_path, db_path)

        # Auto-create missing tables & columns for old backup compatibility
        ensure_db_schema()

        return True, "Backup restored successfully"
    except Exception as e:
        # Try to restore from safety backup
        if safety_backup and os.path.exists(safety_backup):
            try:
                shutil.copy2(safety_backup, db_path)
                ensure_db_schema()
            except Exception:
                pass
        return False, f"Failed to restore backup: {str(e)}"


def list_backups():
    """List available backup files."""
    backup_dir = os.path.join(current_app.instance_path, 'backups')
    if not os.path.exists(backup_dir):
        return []

    backups = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith('.db'):
            path = os.path.join(backup_dir, f)
            backups.append({
                'filename': f,
                'size': os.path.getsize(path),
                'created': datetime.fromtimestamp(os.path.getctime(path)).isoformat(),
            })
    return backups
