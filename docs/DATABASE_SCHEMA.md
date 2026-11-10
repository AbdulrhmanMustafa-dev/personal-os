# ATREES Database Schema

**Version:** 1.0  
**Database:** SQLite (with PostgreSQL migration path)  
**ORM:** SQLAlchemy 2.0  
**Migrations:** Alembic

---

## Design Principles

1. **Normalized** - 3NF where practical, denormalized for read performance
2. **Audit Trail** - All tables have `created_at`, `updated_at`
3. **Soft Deletes** - `deleted_at` for recovery
4. **Idempotent Imports** - Unique constraints on source identifiers
5. **Full-Text Search** - SQLite FTS5 on content tables
6. **Extensible** - JSON columns for flexible metadata

---

## Core Tables

### 1. sources
External data sources connected to ATREES.

```sql
CREATE TABLE sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,           -- 'telegram_mtproto', 'telegram_bot', 'gmail', 'whatsapp', etc.
    display_name VARCHAR(200) NOT NULL,
    connector_type VARCHAR(50),                 -- implementation key: telegram_mtproto, telegram_bot, ...
    enabled BOOLEAN NOT NULL DEFAULT TRUE,       -- eligibility for automatic sync
    type VARCHAR(50) NOT NULL,                   -- 'communication', 'calendar', 'email', 'social', 'ai_chat', 'document'
    status VARCHAR(20) DEFAULT 'disconnected',   -- 'connected', 'disconnected', 'error', 'syncing'
    config JSON NOT NULL DEFAULT '{}',           -- Encrypted credentials, settings
    last_sync_at DATETIME,
    last_sync_status VARCHAR(20),                -- 'success', 'partial', 'failed'
    last_sync_error TEXT,
    sync_cursor JSON,                            -- Platform-specific cursor/token
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
);

CREATE INDEX idx_sources_type ON sources(type);
CREATE INDEX idx_sources_status ON sources(status);
```

`connector_type` is added by migration `002_source_connector_type`; `enabled` is added by `003_source_enabled`. It is intentionally separate from `type`: `type` is a broad domain category (communication, calendar, email, AI chat), while `connector_type` selects a concrete adapter implementation.

### 2. sync_states
Tracks synchronization progress per source.

```sql
CREATE TABLE sync_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    entity_type VARCHAR(50) NOT NULL,            -- 'message', 'contact', 'event', 'task', etc.
    cursor_key VARCHAR(200) NOT NULL,            -- e.g., channel_id, chat_id, label
    cursor_value TEXT NOT NULL,                  -- Last processed ID, timestamp, token
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    status VARCHAR(20) DEFAULT 'running',        -- 'running', 'completed', 'failed'
    error_message TEXT,
    UNIQUE(source_id, entity_type, cursor_key)
);

CREATE INDEX idx_sync_states_source ON sync_states(source_id);
```

### 3. raw_items
Immutable raw records from all sources (write-once, append-only).

```sql
CREATE TABLE raw_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_record_id VARCHAR(500) NOT NULL,      -- Platform-native ID
    source_parent_id VARCHAR(500),               -- Parent (thread, chat, etc.)
    item_type VARCHAR(50) NOT NULL,              -- 'message', 'event', 'task', 'contact', 'email', 'file'
    raw_content JSON NOT NULL,                   -- Full original payload
    content_hash VARCHAR(64) NOT NULL,           -- SHA256 for deduplication
    source_timestamp DATETIME NOT NULL,          -- When the item was created on source
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,
    processing_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    processing_error TEXT,
    UNIQUE(source_id, source_record_id)
);

CREATE INDEX idx_raw_items_source_parent ON raw_items(source_id, source_parent_id);
CREATE INDEX idx_raw_items_type ON raw_items(item_type);
CREATE INDEX idx_raw_items_source_ts ON raw_items(source_id, source_timestamp);
CREATE INDEX idx_raw_items_status ON raw_items(processing_status);
CREATE INDEX idx_raw_items_hash ON raw_items(content_hash);
```

### 4. conversations
Normalized conversation/thread metadata.

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_conversation_id VARCHAR(500) NOT NULL,
    title VARCHAR(500),
    type VARCHAR(50),                            -- 'private', 'group', 'channel', 'email_thread'
    participant_count INTEGER DEFAULT 0,
    is_archived BOOLEAN DEFAULT FALSE,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, source_conversation_id)
);

CREATE INDEX idx_conversations_source ON conversations(source_id);
```

### 5. messages
Normalized messages with extracted content.

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_item_id INTEGER NOT NULL REFERENCES raw_items(id),
    conversation_id INTEGER REFERENCES conversations(id),
    source_message_id VARCHAR(500) NOT NULL,
    source_sender_id VARCHAR(500),
    sender_name VARCHAR(200),
    sender_role VARCHAR(50),                     -- 'user', 'assistant', 'system', 'bot'
    content_text TEXT,                           -- Plain text content
    content_html TEXT,                           -- HTML if available
    language VARCHAR(10),                        -- Detected language
    has_media BOOLEAN DEFAULT FALSE,
    media_metadata JSON,                         -- File info, thumbnails
    reply_to_message_id INTEGER REFERENCES messages(id),
    forward_info JSON,                           -- Forwarded from info
    reaction_summary JSON,                       -- Reactions count
    is_outgoing BOOLEAN DEFAULT FALSE,
    is_edited BOOLEAN DEFAULT FALSE,
    edited_at DATETIME,
    message_timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(raw_item_id)
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_sender ON messages(source_sender_id);
CREATE INDEX idx_messages_timestamp ON messages(message_timestamp);
CREATE INDEX idx_messages_conversation_ts ON messages(conversation_id, message_timestamp);
```

### 6. contacts
People and entities from communications.

```sql
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_contact_id VARCHAR(500) NOT NULL,
    name VARCHAR(200) NOT NULL,
    username VARCHAR(200),
    phone VARCHAR(50),
    email VARCHAR(200),
    avatar_url VARCHAR(500),
    relationship_category VARCHAR(50),           -- 'family', 'friend', 'colleague', 'client', 'service', 'unknown'
    notes TEXT,                                  -- User-added notes
    is_verified BOOLEAN DEFAULT FALSE,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, source_contact_id)
);

CREATE INDEX idx_contacts_source ON contacts(source_id);
CREATE INDEX idx_contacts_name ON contacts(name);
CREATE INDEX idx_contacts_category ON contacts(relationship_category);
```

---

## Task & Calendar Tables

### 7. tasks
Centralized task management with 1-3-5 support.

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id),    -- Origin source (can be NULL for manual)
    source_task_id VARCHAR(500),                 -- External task ID if synced
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(50),                        -- 'work', 'study', 'personal', 'health', 'finance', 'social'
    project_id INTEGER REFERENCES projects(id),
    priority INTEGER DEFAULT 3,                  -- 1=Critical, 2=High, 3=Medium, 4=Low, 5=Someday
    status VARCHAR(20) DEFAULT 'inbox',          -- 'inbox', 'draft', 'needs_review', 'approved', 'scheduled', 'in_progress', 'completed', 'deferred', 'cancelled'
    due_date DATE,
    due_time TIME,
    estimated_duration_minutes INTEGER,
    actual_duration_minutes INTEGER,
    energy_level INTEGER,                        -- 1=Low, 2=Medium, 3=High
    day_plan_slot VARCHAR(20),                   -- 'big', 'medium', 'small', NULL
    day_plan_date DATE,                          -- Date this task is planned for
    confidence REAL DEFAULT 1.0,                 -- Extraction confidence (0-1)
    approval_state VARCHAR(20) DEFAULT 'auto',   -- 'auto', 'pending', 'approved', 'rejected'
    approval_requested_at DATETIME,
    approved_at DATETIME,
    approved_by VARCHAR(100),
    source_message_id INTEGER REFERENCES messages(id),  -- Originating message
    source_event_id INTEGER REFERENCES events(id),      -- Originating event
    tags JSON DEFAULT '[]',
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    deleted_at DATETIME
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_day_plan ON tasks(day_plan_date, day_plan_slot);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_approval ON tasks(approval_state);
```

### 8. projects
Projects that group tasks and events.

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50),                        -- 'work', 'study', 'personal', 'side_hustle', 'learning'
    color VARCHAR(7),                            -- Hex color for UI
    icon VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',         -- 'active', 'on_hold', 'completed', 'archived'
    start_date DATE,
    target_date DATE,
    progress REAL DEFAULT 0.0,                   -- 0-100
    parent_project_id INTEGER REFERENCES projects(id),
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_parent ON projects(parent_project_id);
```

### 9. events
Calendar events with preparation support.

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id),
    source_event_id VARCHAR(500),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    location VARCHAR(500),
    start_datetime DATETIME NOT NULL,
    end_datetime DATETIME,
    timezone VARCHAR(50) DEFAULT 'Africa/Cairo',
    is_all_day BOOLEAN DEFAULT FALSE,
    recurrence_rule TEXT,                        -- RRULE string
    recurrence_id VARCHAR(500),                  -- For exceptions
    status VARCHAR(20) DEFAULT 'confirmed',      -- 'tentative', 'confirmed', 'cancelled'
    visibility VARCHAR(20) DEFAULT 'default',    -- 'default', 'public', 'private', 'confidential'
    meeting_url VARCHAR(500),
    meeting_id VARCHAR(200),
    meeting_password VARCHAR(200),
    organizer_id INTEGER REFERENCES contacts(id),
    attendees JSON DEFAULT '[]',                 -- [{contact_id, status, response}]
    reminders JSON DEFAULT '[]',                 -- [{minutes_before, method}]
    preparation_package_id INTEGER,              -- Link to preparation
    project_id INTEGER REFERENCES projects(id),
    source_message_id INTEGER REFERENCES messages(id),
    requires_preparation BOOLEAN DEFAULT FALSE,
    preparation_notes TEXT,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
);

CREATE INDEX idx_events_start ON events(start_datetime);
CREATE INDEX idx_events_project ON events(project_id);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_source ON events(source_id, source_event_id);
```

### 10. event_preparations
Preparation packages for important events.

```sql
CREATE TABLE event_preparations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    summary TEXT,
    participants JSON DEFAULT '[]',              -- [{contact_id, role, notes}]
    required_documents JSON DEFAULT '[]',        -- [{name, url, status}]
    checklist JSON DEFAULT '[]',                 -- [{item, completed, due_date}]
    related_projects JSON DEFAULT '[]',          -- [project_id]
    links_resources JSON DEFAULT '[]',           -- [{title, url, description}]
    reminders JSON DEFAULT '[]',
    follow_up_tasks JSON DEFAULT '[]',           -- [{title, due_date, assignee}]
    status VARCHAR(20) DEFAULT 'draft',          -- 'draft', 'ready', 'completed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_event_prep_event ON event_preparations(event_id);
```

### 11. reminders
Standalone reminders (not tied to events).

```sql
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    remind_at DATETIME NOT NULL,
    timezone VARCHAR(50) DEFAULT 'Africa/Cairo',
    recurrence_rule TEXT,
    channels JSON DEFAULT '["telegram"]',        -- ['telegram', 'ntfy', 'dashboard']
    priority VARCHAR(20) DEFAULT 'normal',       -- 'critical', 'high', 'normal', 'low'
    status VARCHAR(20) DEFAULT 'pending',        -- 'pending', 'sent', 'dismissed', 'snoozed'
    related_task_id INTEGER REFERENCES tasks(id),
    related_event_id INTEGER REFERENCES events(id),
    related_contact_id INTEGER REFERENCES contacts(id),
    snoozed_until DATETIME,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX idx_reminders_status ON reminders(status);
```

---

## Knowledge & Memory Tables

### 12. knowledge_facts
Extracted and verified facts about the user.

```sql
CREATE TABLE knowledge_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_text TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,               -- 'skill', 'preference', 'goal', 'commitment', 'achievement', 'contact_info', 'project_detail', 'learning'
    subcategory VARCHAR(50),
    evidence_category VARCHAR(30) NOT NULL,      -- 'SELF_REPORTED', 'OBSERVED', 'DEMONSTRATED', 'EXTERNALLY_VERIFIED', 'UNVERIFIED', 'CONFLICTING', 'OUTDATED'
    confidence REAL DEFAULT 0.5,                 -- 0-1
    status VARCHAR(20) DEFAULT 'active',         -- 'active', 'outdated', 'conflicting', 'archived', 'deleted'
    source_platform VARCHAR(50),                 -- 'telegram', 'whatsapp', 'email', 'chatgpt', 'gemini', 'claude', 'manual'
    source_record_id VARCHAR(500),               -- Link to raw_items or messages
    extraction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_reviewed_at DATETIME,
    reviewed_by VARCHAR(100),
    review_notes TEXT,
    conflicting_fact_id INTEGER REFERENCES knowledge_facts(id),
    supersedes_fact_id INTEGER REFERENCES knowledge_facts(id),
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_kf_category ON knowledge_facts(category);
CREATE INDEX idx_kf_evidence ON knowledge_facts(evidence_category);
CREATE INDEX idx_kf_status ON knowledge_facts(status);
CREATE INDEX idx_kf_source ON knowledge_facts(source_platform, source_record_id);
CREATE INDEX idx_kf_confidence ON knowledge_facts(confidence);
```

### 13. evidence
Supporting evidence for facts.

```sql
CREATE TABLE evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id INTEGER NOT NULL REFERENCES knowledge_facts(id),
    source_type VARCHAR(30) NOT NULL,            -- 'message', 'document', 'web_page', 'api_response', 'user_confirmation'
    source_reference VARCHAR(500) NOT NULL,      -- message_id, URL, document_id, etc.
    excerpt TEXT,                                -- Relevant quote
    strength VARCHAR(20) DEFAULT 'supporting',   -- 'definitive', 'strong', 'supporting', 'weak', 'contradictory'
    retrieved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata JSON DEFAULT '{}'
);

CREATE INDEX idx_evidence_fact ON evidence(fact_id);
```

### 14. skills
User skills and learning progress.

```sql
CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50),                        -- 'programming', 'language', 'soft_skill', 'tool', 'framework', 'domain'
    proficiency INTEGER DEFAULT 1,               -- 1=Beginner, 2=Intermediate, 3=Advanced, 4=Expert
    years_experience REAL,
    last_practiced DATE,
    learning_goal TEXT,
    evidence_fact_ids JSON DEFAULT '[]',         -- Links to knowledge_facts
    status VARCHAR(20) DEFAULT 'learning',       -- 'learning', 'maintaining', 'rusty', 'mastered'
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skills_category ON skills(category);
CREATE INDEX idx_skills_status ON skills(status);
```

### 15. goals
User goals with progress tracking.

```sql
CREATE TABLE goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(50),                        -- 'career', 'education', 'health', 'finance', 'personal', 'skill', 'project'
    timeframe VARCHAR(20),                       -- 'daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'long_term'
    target_date DATE,
    status VARCHAR(20) DEFAULT 'active',         -- 'active', 'paused', 'completed', 'abandoned'
    progress REAL DEFAULT 0.0,
    metric VARCHAR(200),                         -- How to measure (e.g., "applications sent", "hours studied")
    target_value REAL,
    current_value REAL DEFAULT 0,
    parent_goal_id INTEGER REFERENCES goals(id),
    related_project_id INTEGER REFERENCES projects(id),
    related_skill_ids JSON DEFAULT '[]',
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_goals_status ON goals(status);
CREATE INDEX idx_goals_category ON goals(category);
CREATE INDEX idx_goals_timeframe ON goals(timeframe);
```

---

## Research Tables

### 16. web_sources
Verified external sources for research.

```sql
CREATE TABLE web_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url VARCHAR(2000) NOT NULL UNIQUE,
    domain VARCHAR(200) NOT NULL,
    title VARCHAR(500),
    publisher VARCHAR(200),
    source_type VARCHAR(50),                     -- 'government', 'university', 'scholarship', 'documentation', 'academic', 'news', 'blog', 'other'
    credibility_score REAL DEFAULT 0.5,          -- 0-1
    last_crawled_at DATETIME,
    crawl_status VARCHAR(20),                    -- 'pending', 'success', 'failed', 'blocked'
    robots_txt_allows BOOLEAN,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ws_domain ON web_sources(domain);
CREATE INDEX idx_ws_type ON web_sources(source_type);
CREATE INDEX idx_ws_credibility ON web_sources(credibility_score);
```

### 17. research_reports
Structured research outputs.

```sql
CREATE TABLE research_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500) NOT NULL,
    query TEXT NOT NULL,
    category VARCHAR(50),                        -- 'scholarship', 'internship', 'university', 'programming', 'cybersecurity', 'tech_news', 'career', 'personal'
    summary TEXT,
    findings JSON DEFAULT '[]',                  -- [{claim, evidence, confidence, source_ids}]
    source_ids JSON DEFAULT '[]',                -- web_sources IDs
    status VARCHAR(20) DEFAULT 'draft',          -- 'draft', 'verified', 'archived'
    confidence REAL DEFAULT 0.5,
    requested_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rr_category ON research_reports(category);
CREATE INDEX idx_rr_status ON research_reports(status);
```

### 18. research_claims
Individual verified claims from research.

```sql
CREATE TABLE research_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES research_reports(id),
    claim_text TEXT NOT NULL,
    source_id INTEGER REFERENCES web_sources(id),
    source_url VARCHAR(2000),
    source_title VARCHAR(500),
    publisher VARCHAR(200),
    publication_date DATE,
    event_date DATE,                             -- If different from publication
    retrieval_date DATE DEFAULT CURRENT_DATE,
    supporting_text TEXT,
    verification_status VARCHAR(20) DEFAULT 'unverified',  -- 'verified', 'unverified', 'contradicted', 'outdated'
    confidence REAL DEFAULT 0.5,
    contradictory_evidence TEXT,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rc_report ON research_claims(report_id);
CREATE INDEX idx_rc_verification ON research_claims(verification_status);
```

---

## Notification & Automation Tables

### 19. notifications
Notification log and delivery tracking.

```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500) NOT NULL,
    body TEXT,
    priority VARCHAR(20) DEFAULT 'normal',       -- 'critical', 'high', 'normal', 'low'
    channels JSON DEFAULT '["telegram"]',        -- ['telegram', 'ntfy', 'dashboard', 'email']
    status VARCHAR(20) DEFAULT 'pending',        -- 'pending', 'sent', 'failed', 'dismissed'
    sent_at DATETIME,
    delivered_at DATETIME,
    read_at DATETIME,
    dismissed_at DATETIME,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    related_task_id INTEGER REFERENCES tasks(id),
    related_event_id INTEGER REFERENCES events(id),
    related_reminder_id INTEGER REFERENCES reminders(id),
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notif_status ON notifications(status);
CREATE INDEX idx_notif_priority ON notifications(priority);
CREATE INDEX idx_notif_created ON notifications(created_at);
```

### 20. automation_jobs
Scheduled background jobs.

```sql
CREATE TABLE automation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    job_type VARCHAR(50) NOT NULL,               -- 'sync', 'extract', 'briefing', 'research', 'reminder', 'cleanup'
    schedule_cron VARCHAR(100),                  -- Cron expression
    schedule_interval_seconds INTEGER,           -- Alternative to cron
    is_enabled BOOLEAN DEFAULT TRUE,
    last_run_at DATETIME,
    last_run_status VARCHAR(20),                 -- 'success', 'partial', 'failed', 'skipped'
    last_run_duration_ms INTEGER,
    last_run_error TEXT,
    next_run_at DATETIME,
    retry_policy JSON DEFAULT '{"max_retries": 3, "backoff_factor": 2}',
    timeout_seconds INTEGER DEFAULT 300,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aj_enabled ON automation_jobs(is_enabled);
CREATE INDEX idx_aj_next_run ON automation_jobs(next_run_at);
```

### 21. audit_logs
Security and operation audit trail.

```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action VARCHAR(100) NOT NULL,                -- 'create', 'update', 'delete', 'sync', 'approve', 'send', 'login', 'export'
    entity_type VARCHAR(50),                     -- 'task', 'event', 'fact', 'source', 'notification'
    entity_id INTEGER,
    user_identifier VARCHAR(100),                -- 'system', 'user', 'telegram_bot', 'api_key_xxx'
    details JSON DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_logs(user_identifier);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
```

---

## User Preferences

### 22. user_preferences
System configuration per user.

```sql
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(100) NOT NULL UNIQUE,
    value JSON NOT NULL,
    category VARCHAR(50),                        -- 'ai', 'notifications', 'calendar', 'tasks', 'privacy', 'ui', 'sync'
    description TEXT,
    is_sensitive BOOLEAN DEFAULT FALSE,          -- Encrypt in storage
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Default preferences to insert:
-- ai.provider_preference: ["local", "groq", "cerebras", "openrouter", "gemini"]
-- ai.local_model: "llama3.1:8b"
-- ai.cloud_enabled: true
-- notifications.quiet_hours_start: "22:00"
-- notifications.quiet_hours_end: "08:00"
-- notifications.priority_threshold: "normal"
-- calendar.timezone: "Africa/Cairo"
-- calendar.default_reminder_minutes: 15
-- tasks.default_priority: 3
-- tasks.day_plan_method: "1-3-5"
-- privacy.encrypt_backups: true
-- privacy.retention_days: 365
-- sync.auto_sync_interval_minutes: 30
-- ui.theme: "system"
-- ui.language: "ar"
```

---

## Full-Text Search (SQLite FTS5)

### 23. messages_fts
```sql
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content_text,
    sender_name,
    conversation_title,
    content=messages,
    content_rowid=id
);

-- Triggers to keep FTS in sync
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content_text, sender_name, conversation_title)
    VALUES (new.id, new.content_text, 
            (SELECT name FROM contacts WHERE source_contact_id = new.source_sender_id LIMIT 1),
            (SELECT title FROM conversations WHERE id = new.conversation_id));
END;

CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content_text, sender_name, conversation_title)
    VALUES ('delete', old.id, old.content_text, '', '');
END;

CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content_text, sender_name, conversation_title)
    VALUES ('delete', old.id, old.content_text, '', '');
    INSERT INTO messages_fts(rowid, content_text, sender_name, conversation_title)
    VALUES (new.id, new.content_text,
            (SELECT name FROM contacts WHERE source_contact_id = new.source_sender_id LIMIT 1),
            (SELECT title FROM conversations WHERE id = new.conversation_id));
END;
```

### 24. knowledge_facts_fts
```sql
CREATE VIRTUAL TABLE knowledge_facts_fts USING fts5(
    fact_text,
    category,
    subcategory,
    content=knowledge_facts,
    content_rowid=id
);
```

### 25. tasks_fts
```sql
CREATE VIRTUAL TABLE tasks_fts USING fts5(
    title,
    description,
    tags,
    content=tasks,
    content_rowid=id
);
```

---

## Views for Common Queries

### 26. v_today_tasks
```sql
CREATE VIEW v_today_tasks AS
SELECT t.*, p.name as project_name, p.color as project_color
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
WHERE t.day_plan_date = date('now', 'localtime')
  AND t.status IN ('approved', 'scheduled', 'in_progress')
  AND t.deleted_at IS NULL
ORDER BY 
  CASE t.day_plan_slot WHEN 'big' THEN 1 WHEN 'medium' THEN 2 WHEN 'small' THEN 3 ELSE 4 END,
  t.priority;
```

### 27. v_upcoming_events
```sql
CREATE VIEW v_upcoming_events AS
SELECT e.*, ep.summary as prep_summary, ep.status as prep_status
FROM events e
LEFT JOIN event_preparations ep ON e.id = ep.event_id
WHERE e.start_datetime >= datetime('now', 'localtime')
  AND e.status != 'cancelled'
  AND e.deleted_at IS NULL
ORDER BY e.start_datetime
LIMIT 50;
```

### 28. v_active_knowledge
```sql
CREATE VIEW v_active_knowledge AS
SELECT kf.*, e.excerpt, e.strength, e.source_type, e.source_reference
FROM knowledge_facts kf
LEFT JOIN evidence e ON kf.id = e.fact_id
WHERE kf.status = 'active'
  AND kf.confidence >= 0.5
ORDER BY kf.category, kf.confidence DESC;
```

---

## Migration Notes

### Initial Migration (001_initial.py)
Creates all tables above in dependency order.

### Indexes
All foreign keys should have indexes. Composite indexes for common query patterns.

### Triggers
- `updated_at` auto-update triggers on all tables
- FTS5 sync triggers

### Encryption
Sensitive columns (config in sources, value in user_preferences) should be encrypted at application layer using Fernet/AES-GCM.

### PostgreSQL Migration Path
- Replace `AUTOINCREMENT` with `SERIAL` / `IDENTITY`
- Replace `DATETIME` with `TIMESTAMP WITH TIME ZONE`
- Replace `JSON` with `JSONB`
- FTS5 → pg_trgm + GIN indexes or pgvector for semantic search
- Boolean: SQLite uses 0/1, PostgreSQL uses true/false