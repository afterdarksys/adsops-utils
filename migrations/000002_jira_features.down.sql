-- =====================================================
-- MIGRATION 002 ROLLBACK: JIRA-like Features
-- =====================================================

-- Drop triggers first
DROP TRIGGER IF EXISTS update_failed_signups_timestamp ON failed_signup_attempts;
DROP TRIGGER IF EXISTS update_employee_profiles_timestamp ON employee_profiles;
DROP TRIGGER IF EXISTS update_repositories_timestamp ON repositories;
DROP TRIGGER IF EXISTS update_contacts_timestamp ON contacts;
DROP TRIGGER IF EXISTS update_customers_timestamp ON customers;
DROP TRIGGER IF EXISTS update_groups_timestamp ON groups;
DROP TRIGGER IF EXISTS update_projects_timestamp ON projects;
DROP TRIGGER IF EXISTS no_audit_deletion ON ticket_audit_log;

-- Drop functions
DROP FUNCTION IF EXISTS track_failed_signup(VARCHAR, INET);
DROP FUNCTION IF EXISTS log_ticket_access(UUID, UUID, VARCHAR, INET, TEXT, JSONB);
DROP FUNCTION IF EXISTS check_ticket_access(UUID, UUID, ticket_acl_role);
DROP FUNCTION IF EXISTS prevent_audit_deletion();

-- Drop views
DROP VIEW IF EXISTS v_ticket_queue;
DROP VIEW IF EXISTS v_user_accessible_tickets;

-- Remove columns from change_tickets
ALTER TABLE change_tickets
    DROP COLUMN IF EXISTS project_id,
    DROP COLUMN IF EXISTS owning_group_id,
    DROP COLUMN IF EXISTS customer_id,
    DROP COLUMN IF EXISTS parent_ticket_id,
    DROP COLUMN IF EXISTS epic_id,
    DROP COLUMN IF EXISTS story_points,
    DROP COLUMN IF EXISTS time_estimate_hours,
    DROP COLUMN IF EXISTS time_spent_hours,
    DROP COLUMN IF EXISTS labels,
    DROP COLUMN IF EXISTS watchers,
    DROP COLUMN IF EXISTS external_reference,
    DROP COLUMN IF EXISTS acl_inheritance,
    DROP COLUMN IF EXISTS is_confidential;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS failed_signup_attempts;
DROP TABLE IF EXISTS ticket_audit_log;
DROP TABLE IF EXISTS employee_profiles;
DROP TABLE IF EXISTS ticket_acls;
DROP TABLE IF EXISTS ticket_repositories;
DROP TABLE IF EXISTS repositories;
DROP TABLE IF EXISTS contacts;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS group_members;
DROP TABLE IF EXISTS groups;
DROP TABLE IF EXISTS projects;

-- Drop enum types
DROP TYPE IF EXISTS employee_type;
DROP TYPE IF EXISTS security_clearance;
DROP TYPE IF EXISTS contact_type;
DROP TYPE IF EXISTS ticket_acl_role;
