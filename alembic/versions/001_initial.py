"""
Initial migration for ATREES.

Creates all tables for the ATREES Personal Life OS.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='disconnected'),
        sa.Column('config', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(20), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('sync_cursor', sqlite.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_sources_name'),
    )
    op.create_index('ix_sources_type', 'sources', ['type'])
    op.create_index('ix_sources_status', 'sources', ['status'])

    # Create sync_states table
    op.create_table(
        'sync_states',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('cursor_key', sa.String(200), nullable=False),
        sa.Column('cursor_value', sa.Text(), nullable=False),
        sa.Column('items_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_id', 'entity_type', 'cursor_key', name='uq_sync_state_source_entity_cursor'),
    )
    op.create_index('ix_sync_states_source', 'sync_states', ['source_id'])
    op.create_index('ix_sync_states_source_entity', 'sync_states', ['source_id', 'entity_type'])

    # Create raw_items table
    op.create_table(
        'raw_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('source_record_id', sa.String(500), nullable=False),
        sa.Column('source_parent_id', sa.String(500), nullable=True),
        sa.Column('item_type', sa.String(50), nullable=False),
        sa.Column('raw_content', sqlite.JSON(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_id', 'source_record_id', name='uq_raw_item_source_record'),
    )
    op.create_index('ix_raw_items_source_parent', 'raw_items', ['source_id', 'source_parent_id'])
    op.create_index('ix_raw_items_type', 'raw_items', ['item_type'])
    op.create_index('ix_raw_items_source_ts', 'raw_items', ['source_id', 'source_timestamp'])
    op.create_index('ix_raw_items_status', 'raw_items', ['processing_status'])
    op.create_index('ix_raw_items_hash', 'raw_items', ['content_hash'])

    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('source_conversation_id', sa.String(500), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('type', sa.String(50), nullable=True),
        sa.Column('participant_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_id', 'source_conversation_id', name='uq_conversation_source'),
    )
    op.create_index('ix_conversations_source', 'conversations', ['source_id'])

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('raw_item_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('source_message_id', sa.String(500), nullable=False),
        sa.Column('source_sender_id', sa.String(500), nullable=True),
        sa.Column('sender_name', sa.String(200), nullable=True),
        sa.Column('sender_role', sa.String(50), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('has_media', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('media_metadata', sqlite.JSON(), nullable=True),
        sa.Column('reply_to_message_id', sa.Integer(), nullable=True),
        sa.Column('forward_info', sqlite.JSON(), nullable=True),
        sa.Column('reaction_summary', sqlite.JSON(), nullable=True),
        sa.Column('is_outgoing', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_edited', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('message_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['raw_item_id'], ['raw_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reply_to_message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('raw_item_id', name='uq_message_raw_item'),
    )
    op.create_index('ix_messages_conversation', 'messages', ['conversation_id'])
    op.create_index('ix_messages_sender', 'messages', ['source_sender_id'])
    op.create_index('ix_messages_timestamp', 'messages', ['message_timestamp'])
    op.create_index('ix_messages_conversation_ts', 'messages', ['conversation_id', 'message_timestamp'])
    op.create_index('ix_messages_outgoing', 'messages', ['is_outgoing'])

    # Create contacts table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('source_contact_id', sa.String(500), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('username', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('relationship_category', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_id', 'source_contact_id', name='uq_contact_source'),
    )
    op.create_index('ix_contacts_source', 'contacts', ['source_id'])
    op.create_index('ix_contacts_name', 'contacts', ['name'])
    op.create_index('ix_contacts_category', 'contacts', ['relationship_category'])
    op.create_index('ix_contacts_email', 'contacts', ['email'])

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('parent_project_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_project_id'], ['projects.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_projects_status', 'projects', ['status'])
    op.create_index('ix_projects_parent', 'projects', ['parent_project_id'])
    op.create_index('ix_projects_category', 'projects', ['category'])

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_task_id', sa.String(500), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('status', sa.String(20), nullable=False, server_default='inbox'),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('due_time', sa.Time(), nullable=True),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('actual_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('energy_level', sa.Integer(), nullable=True),
        sa.Column('day_plan_slot', sa.String(20), nullable=True),
        sa.Column('day_plan_date', sa.Date(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('approval_state', sa.String(20), nullable=False, server_default='auto'),
        sa.Column('approval_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('source_message_id', sa.Integer(), nullable=True),
        sa.Column('source_event_id', sa.Integer(), nullable=True),
        sa.Column('tags', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_event_id'], ['events.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_due_date', 'tasks', ['due_date'])
    op.create_index('ix_tasks_project', 'tasks', ['project_id'])
    op.create_index('ix_tasks_day_plan', 'tasks', ['day_plan_date', 'day_plan_slot'])
    op.create_index('ix_tasks_priority', 'tasks', ['priority'])
    op.create_index('ix_tasks_approval', 'tasks', ['approval_state'])
    op.create_index('ix_tasks_source', 'tasks', ['source_id', 'source_task_id'])

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_event_id', sa.String(500), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('start_datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_datetime', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Africa/Cairo'),
        sa.Column('is_all_day', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('recurrence_rule', sa.Text(), nullable=True),
        sa.Column('recurrence_id', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='confirmed'),
        sa.Column('visibility', sa.String(20), nullable=False, server_default='default'),
        sa.Column('meeting_url', sa.String(500), nullable=True),
        sa.Column('meeting_id', sa.String(200), nullable=True),
        sa.Column('meeting_password', sa.String(200), nullable=True),
        sa.Column('organizer_id', sa.Integer(), nullable=True),
        sa.Column('attendees', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('reminders', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('preparation_package_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('source_message_id', sa.Integer(), nullable=True),
        sa.Column('requires_preparation', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('preparation_notes', sa.Text(), nullable=True),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organizer_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['preparation_package_id'], ['event_preparations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_events_start', 'events', ['start_datetime'])
    op.create_index('ix_events_project', 'events', ['project_id'])
    op.create_index('ix_events_status', 'events', ['status'])
    op.create_index('ix_events_source', 'events', ['source_id', 'source_event_id'])

    # Create event_preparations table
    op.create_table(
        'event_preparations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('participants', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('required_documents', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('checklist', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('related_projects', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('links_resources', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('reminders', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('follow_up_tasks', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('event_id', name='uq_event_prep_event'),
    )
    op.create_index('ix_event_prep_event', 'event_preparations', ['event_id'])

    # Create reminders table
    op.create_table(
        'reminders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('remind_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Africa/Cairo'),
        sa.Column('recurrence_rule', sa.Text(), nullable=True),
        sa.Column('channels', sqlite.JSON(), nullable=False, server_default='["telegram"]'),
        sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('related_task_id', sa.Integer(), nullable=True),
        sa.Column('related_event_id', sa.Integer(), nullable=True),
        sa.Column('related_contact_id', sa.Integer(), nullable=True),
        sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['related_task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_event_id'], ['events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_contact_id'], ['contacts.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_reminders_remind_at', 'reminders', ['remind_at'])
    op.create_index('ix_reminders_status', 'reminders', ['status'])

    # Create knowledge_facts table
    op.create_table(
        'knowledge_facts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fact_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('subcategory', sa.String(50), nullable=True),
        sa.Column('evidence_category', sa.String(30), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('source_platform', sa.String(50), nullable=True),
        sa.Column('source_record_id', sa.String(500), nullable=True),
        sa.Column('extraction_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('conflicting_fact_id', sa.Integer(), nullable=True),
        sa.Column('supersedes_fact_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conflicting_fact_id'], ['knowledge_facts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['supersedes_fact_id'], ['knowledge_facts.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_kf_category', 'knowledge_facts', ['category'])
    op.create_index('ix_kf_evidence', 'knowledge_facts', ['evidence_category'])
    op.create_index('ix_kf_status', 'knowledge_facts', ['status'])
    op.create_index('ix_kf_source', 'knowledge_facts', ['source_platform', 'source_record_id'])
    op.create_index('ix_kf_confidence', 'knowledge_facts', ['confidence'])

    # Create evidence table
    op.create_table(
        'evidence',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fact_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(30), nullable=False),
        sa.Column('source_reference', sa.String(500), nullable=False),
        sa.Column('excerpt', sa.Text(), nullable=True),
        sa.Column('strength', sa.String(20), nullable=False, server_default='supporting'),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['fact_id'], ['knowledge_facts.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_evidence_fact', 'evidence', ['fact_id'])

    # Create skills table
    op.create_table(
        'skills',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('proficiency', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('years_experience', sa.Float(), nullable=True),
        sa.Column('last_practiced', sa.Date(), nullable=True),
        sa.Column('learning_goal', sa.Text(), nullable=True),
        sa.Column('evidence_fact_ids', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='learning'),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skills_category', 'skills', ['category'])
    op.create_index('ix_skills_status', 'skills', ['status'])

    # Create goals table
    op.create_table(
        'goals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('timeframe', sa.String(20), nullable=True),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('progress', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('metric', sa.String(200), nullable=True),
        sa.Column('target_value', sa.Float(), nullable=True),
        sa.Column('current_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('parent_goal_id', sa.Integer(), nullable=True),
        sa.Column('related_project_id', sa.Integer(), nullable=True),
        sa.Column('related_skill_ids', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_goal_id'], ['goals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_project_id'], ['projects.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_goals_status', 'goals', ['status'])
    op.create_index('ix_goals_category', 'goals', ['category'])
    op.create_index('ix_goals_timeframe', 'goals', ['timeframe'])

    # Create web_sources table
    op.create_table(
        'web_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('url', sa.String(2000), nullable=False),
        sa.Column('domain', sa.String(200), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('publisher', sa.String(200), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=True),
        sa.Column('credibility_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('last_crawled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('crawl_status', sa.String(20), nullable=True),
        sa.Column('robots_txt_allows', sa.Boolean(), nullable=True),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url', name='uq_web_source_url'),
    )
    op.create_index('ix_ws_domain', 'web_sources', ['domain'])
    op.create_index('ix_ws_type', 'web_sources', ['source_type'])
    op.create_index('ix_ws_credibility', 'web_sources', ['credibility_score'])

    # Create research_reports table
    op.create_table(
        'research_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('findings', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('source_ids', sqlite.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('requested_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rr_category', 'research_reports', ['category'])
    op.create_index('ix_rr_status', 'research_reports', ['status'])

    # Create research_claims table
    op.create_table(
        'research_claims',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_url', sa.String(2000), nullable=True),
        sa.Column('source_title', sa.String(500), nullable=True),
        sa.Column('publisher', sa.String(200), nullable=True),
        sa.Column('publication_date', sa.Date(), nullable=True),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('retrieval_date', sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column('supporting_text', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.String(20), nullable=False, server_default='unverified'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('contradictory_evidence', sa.Text(), nullable=True),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['report_id'], ['research_reports.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['web_sources.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_rc_report', 'research_claims', ['report_id'])
    op.create_index('ix_rc_verification', 'research_claims', ['verification_status'])

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('channels', sqlite.JSON(), nullable=False, server_default='["telegram"]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('related_task_id', sa.Integer(), nullable=True),
        sa.Column('related_event_id', sa.Integer(), nullable=True),
        sa.Column('related_reminder_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['related_task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_event_id'], ['events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_reminder_id'], ['reminders.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_notif_status', 'notifications', ['status'])
    op.create_index('ix_notif_priority', 'notifications', ['priority'])
    op.create_index('ix_notif_created', 'notifications', ['created_at'])

    # Create automation_jobs table
    op.create_table(
        'automation_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('schedule_cron', sa.String(100), nullable=True),
        sa.Column('schedule_interval_seconds', sa.Integer(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', sa.String(20), nullable=True),
        sa.Column('last_run_duration_ms', sa.Integer(), nullable=True),
        sa.Column('last_run_error', sa.Text(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_policy', sqlite.JSON(), nullable=False, server_default='{"max_retries": 3, "backoff_factor": 2}'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('metadata', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_automation_job_name'),
    )
    op.create_index('ix_aj_enabled', 'automation_jobs', ['is_enabled'])
    op.create_index('ix_aj_next_run', 'automation_jobs', ['next_run_at'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('user_identifier', sa.String(100), nullable=False),
        sa.Column('details', sqlite.JSON(), nullable=False, server_default='{}'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_entity', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_user', 'audit_logs', ['user_identifier'])
    op.create_index('ix_audit_created', 'audit_logs', ['created_at'])

    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sqlite.JSON(), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_user_preference_key'),
    )
    op.create_index('ix_pref_category', 'user_preferences', ['category'])

    # Create FTS5 virtual tables for full-text search
    op.execute("""
        CREATE VIRTUAL TABLE messages_fts USING fts5(
            content_text,
            sender_name,
            conversation_title,
            content=messages,
            content_rowid=id
        )
    """)

    op.execute("""
        CREATE VIRTUAL TABLE knowledge_facts_fts USING fts5(
            fact_text,
            category,
            subcategory,
            content=knowledge_facts,
            content_rowid=id
        )
    """)

    op.execute("""
        CREATE VIRTUAL TABLE tasks_fts USING fts5(
            title,
            description,
            tags,
            content=tasks,
            content_rowid=id
        )
    """)

    # Create triggers for FTS5 sync
    op.execute("""
        CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content_text, sender_name, conversation_title)
            VALUES (new.id, new.content_text,
                (SELECT name FROM contacts WHERE source_contact_id = new.source_sender_id LIMIT 1),
                (SELECT title FROM conversations WHERE id = new.conversation_id));
        END
    """)

    op.execute("""
        CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content_text, sender_name, conversation_title)
            VALUES ('delete', old.id, old.content_text, '', '');
        END
    """)

    op.execute("""
        CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content_text, sender_name, conversation_title)
            VALUES ('delete', old.id, old.content_text, '', '');
            INSERT INTO messages_fts(rowid, content_text, sender_name, conversation_title)
            VALUES (new.id, new.content_text,
                (SELECT name FROM contacts WHERE source_contact_id = new.source_sender_id LIMIT 1),
                (SELECT title FROM conversations WHERE id = new.conversation_id));
        END
    """)

    op.execute("""
        CREATE TRIGGER kf_ai AFTER INSERT ON knowledge_facts BEGIN
            INSERT INTO knowledge_facts_fts(rowid, fact_text, category, subcategory)
            VALUES (new.id, new.fact_text, new.category, new.subcategory);
        END
    """)

    op.execute("""
        CREATE TRIGGER kf_ad AFTER DELETE ON knowledge_facts BEGIN
            INSERT INTO knowledge_facts_fts(knowledge_facts_fts, rowid, fact_text, category, subcategory)
            VALUES ('delete', old.id, old.fact_text, '', '');
        END
    """)

    op.execute("""
        CREATE TRIGGER kf_au AFTER UPDATE ON knowledge_facts BEGIN
            INSERT INTO knowledge_facts_fts(knowledge_facts_fts, rowid, fact_text, category, subcategory)
            VALUES ('delete', old.id, old.fact_text, '', '');
            INSERT INTO knowledge_facts_fts(rowid, fact_text, category, subcategory)
            VALUES (new.id, new.fact_text, new.category, new.subcategory);
        END
    """)

    op.execute("""
        CREATE TRIGGER tasks_ai AFTER INSERT ON tasks BEGIN
            INSERT INTO tasks_fts(rowid, title, description, tags)
            VALUES (new.id, new.title, new.description, json_group_array(new.tags));
        END
    """)

    op.execute("""
        CREATE TRIGGER tasks_ad AFTER DELETE ON tasks BEGIN
            INSERT INTO tasks_fts(tasks_fts, rowid, title, description, tags)
            VALUES ('delete', old.id, old.title, old.description, '');
        END
    """)

    op.execute("""
        CREATE TRIGGER tasks_au AFTER UPDATE ON tasks BEGIN
            INSERT INTO tasks_fts(tasks_fts, rowid, title, description, tags)
            VALUES ('delete', old.id, old.title, old.description, '');
            INSERT INTO tasks_fts(rowid, title, description, tags)
            VALUES (new.id, new.title, new.description, json_group_array(new.tags));
        END
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS tasks_au")
    op.execute("DROP TRIGGER IF EXISTS tasks_ad")
    op.execute("DROP TRIGGER IF EXISTS tasks_ai")
    op.execute("DROP TRIGGER IF EXISTS kf_au")
    op.execute("DROP TRIGGER IF EXISTS kf_ad")
    op.execute("DROP TRIGGER IF EXISTS kf_ai")
    op.execute("DROP TRIGGER IF EXISTS messages_au")
    op.execute("DROP TRIGGER IF EXISTS messages_ad")
    op.execute("DROP TRIGGER IF EXISTS messages_ai")

    # Drop FTS tables
    op.execute("DROP TABLE IF EXISTS tasks_fts")
    op.execute("DROP TABLE IF EXISTS knowledge_facts_fts")
    op.execute("DROP TABLE IF EXISTS messages_fts")

    # Drop tables in reverse order
    op.drop_table('user_preferences')
    op.drop_table('audit_logs')
    op.drop_table('automation_jobs')
    op.drop_table('notifications')
    op.drop_table('research_claims')
    op.drop_table('research_reports')
    op.drop_table('web_sources')
    op.drop_table('goals')
    op.drop_table('skills')
    op.drop_table('evidence')
    op.drop_table('knowledge_facts')
    op.drop_table('reminders')
    op.drop_table('event_preparations')
    op.drop_table('events')
    op.drop_table('tasks')
    op.drop_table('projects')
    op.drop_table('contacts')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('raw_items')
    op.drop_table('sync_states')
    op.drop_table('sources')