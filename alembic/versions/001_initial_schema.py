"""initial schema

Revision ID: 001
Revises: 
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create missions table
    op.create_table(
        'missions',
        sa.Column('id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('objective', sa.Text, nullable=False),
        sa.Column('phase', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('priority', sa.String(16), nullable=False),
        sa.Column('risk_level', sa.String(16), nullable=False),
        sa.Column('current_loop_iteration', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_loop_iterations', sa.Integer, nullable=False, server_default='10'),
        sa.Column('approval_state', sa.String(32), nullable=False),
        sa.Column('assigned_runtime_id', sa.String(64), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime, nullable=True),
        sa.Column('recovery_state', sa.String(64), nullable=True),
        sa.Column('metadata_json', sa.Text, nullable=True),
        sa.Column('error_summary', sa.Text, nullable=True),
    )
    
    op.create_index('idx_missions_phase', 'missions', ['phase'])
    op.create_index('idx_missions_status', 'missions', ['status'])
    op.create_index('idx_missions_approval_state', 'missions', ['approval_state'])
    op.create_index('idx_missions_updated_at', 'missions', ['updated_at'])

    # Create mission_events table
    op.create_table(
        'mission_events',
        sa.Column('id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('phase', sa.String(32), nullable=True),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('payload_json', sa.Text, nullable=True),
        sa.Column('sequence_number', sa.Integer, nullable=False),
        
        sa.ForeignKeyConstraint(['mission_id'], ['missions.id'], ondelete='CASCADE'),
    )
    
    op.create_index('idx_mission_events_mission_seq', 'mission_events', ['mission_id', 'sequence_number'], unique=True)
    op.create_index('idx_mission_events_mission_id', 'mission_events', ['mission_id'])
    op.create_index('idx_mission_events_event_type', 'mission_events', ['event_type'])
    op.create_index('idx_mission_events_created_at', 'mission_events', ['created_at'])

    # Create approvals table
    op.create_table(
        'approvals',
        sa.Column('id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(64), nullable=False),
        sa.Column('approval_type', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('requested_at', sa.DateTime, nullable=False),
        sa.Column('responded_at', sa.DateTime, nullable=True),
        sa.Column('response_note', sa.Text, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('payload_json', sa.Text, nullable=True),
        
        sa.ForeignKeyConstraint(['mission_id'], ['missions.id'], ondelete='CASCADE'),
    )
    
    op.create_index('idx_approvals_mission_id', 'approvals', ['mission_id'])
    op.create_index('idx_approvals_status', 'approvals', ['status'])
    op.create_index('idx_approvals_requested_at', 'approvals', ['requested_at'])

    # Create artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(64), nullable=False),
        sa.Column('artifact_type', sa.String(32), nullable=False),
        sa.Column('logical_name', sa.String(255), nullable=False),
        sa.Column('relative_path', sa.String(512), nullable=True),
        sa.Column('mime_type', sa.String(128), nullable=True),
        sa.Column('size_bytes', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('metadata_json', sa.Text, nullable=True),
        
        sa.ForeignKeyConstraint(['mission_id'], ['missions.id'], ondelete='CASCADE'),
    )
    
    op.create_index('idx_artifacts_mission_id', 'artifacts', ['mission_id'])
    op.create_index('idx_artifacts_artifact_type', 'artifacts', ['artifact_type'])
    op.create_index('idx_artifacts_created_at', 'artifacts', ['created_at'])

    # Create runtime_leases table
    op.create_table(
        'runtime_leases',
        sa.Column('id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(64), nullable=False),
        sa.Column('runtime_id', sa.String(64), nullable=False),
        sa.Column('leased_at', sa.DateTime, nullable=False),
        sa.Column('heartbeat_at', sa.DateTime, nullable=False),
        sa.Column('lease_status', sa.String(32), nullable=False),
        
        sa.ForeignKeyConstraint(['mission_id'], ['missions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('mission_id', name='uq_runtime_leases_mission_id'),
    )
    
    op.create_index('idx_runtime_leases_mission_id', 'runtime_leases', ['mission_id'])
    op.create_index('idx_runtime_leases_status', 'runtime_leases', ['lease_status'])
    op.create_index('idx_runtime_leases_heartbeat_at', 'runtime_leases', ['heartbeat_at'])


def downgrade() -> None:
    op.drop_table('runtime_leases')
    op.drop_table('artifacts')
    op.drop_table('approvals')
    op.drop_table('mission_events')
    op.drop_table('missions')