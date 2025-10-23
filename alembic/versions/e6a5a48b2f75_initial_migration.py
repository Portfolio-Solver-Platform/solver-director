"""Initial migration

Revision ID: e6a5a48b2f75
Revises: 
Create Date: 2025-10-21 14:20:25.689874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6a5a48b2f75'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create solver_images table
    op.create_table(
        'solver_images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('image_path', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create groups table
    op.create_table(
        'groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create solvers table
    op.create_table(
        'solvers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('solver_images_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['solver_images_id'], ['solver_images.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create solver_supported_groups association table
    op.create_table(
        'solver_supported_groups',
        sa.Column('solver_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['solver_id'], ['solvers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('solver_id', 'group_id')
    )

    # Create problems table
    op.create_table(
        'problems',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=True),
        sa.Column('file_data', sa.LargeBinary(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('is_instances_self_contained', sa.Boolean(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create instances table
    op.create_table(
        'instances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_data', sa.LargeBinary(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('instances')
    op.drop_table('problems')
    op.drop_table('solver_supported_groups')
    op.drop_table('solvers')
    op.drop_table('groups')
    op.drop_table('solver_images')
