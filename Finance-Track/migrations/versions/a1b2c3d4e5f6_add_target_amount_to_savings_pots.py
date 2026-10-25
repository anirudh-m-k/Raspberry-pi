"""Add target_amount to savings_pots

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2026-10-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add target_amount column — nullable, no default, existing rows get NULL (shows '+' UI)
    with op.batch_alter_table('savings_pots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_amount', sa.Numeric(precision=12, scale=2), nullable=True))


def downgrade():
    with op.batch_alter_table('savings_pots', schema=None) as batch_op:
        batch_op.drop_column('target_amount')
