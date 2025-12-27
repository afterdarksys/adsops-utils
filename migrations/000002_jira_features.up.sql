-- =====================================================
-- MIGRATION 002: JIRA-like Features
-- Projects, Repositories, Contacts, ACLs, Employee Directory
-- =====================================================

-- =====================================================
-- ENUM TYPES
-- =====================================================

CREATE TYPE ticket_acl_role AS ENUM (
    'viewer',           -- Can view ticket
    'commenter',        -- Can view + comment
    'editor',           -- Can view + comment + edit
    'owner',            -- Full access to ticket
    'admin',            -- Full access + can manage ACLs
    'management',       -- Management access for oversight
    'legal',            -- Legal team access
    'auditor'           -- Read-only audit access
);

CREATE TYPE contact_type AS ENUM (
    'email',
    'phone',
    'discord',
    'slack',
    'teams',
    'fax'
);

CREATE TYPE security_clearance AS ENUM (
    'none',
    'confidential',
    'secret',
    'top_secret',
    'ts_sci'
);

CREATE TYPE employee_type AS ENUM (
    'full_time',
    'contractor',
    'consultant',
    'intern',
    'vendor'
);

-- =====================================================
-- PROJECTS (Like JIRA Projects)
-- =====================================================

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    project_key VARCHAR(10) NOT NULL,  -- e.g., "INFRA", "SEC", "OPS"
    name VARCHAR(255) NOT NULL,
    description TEXT,
    lead_user_id UUID REFERENCES users(id),
    default_assignee_id UUID REFERENCES users(id),
    owning_group_id UUID,  -- References groups table below
    customer_id UUID,      -- External customer this project is for
    is_active BOOLEAN DEFAULT true,
    icon_url VARCHAR(512),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    UNIQUE(organization_id, project_key)
);

CREATE INDEX idx_projects_org ON projects(organization_id);
CREATE INDEX idx_projects_key ON projects(project_key);
CREATE INDEX idx_projects_lead ON projects(lead_user_id);

-- =====================================================
-- GROUPS (Like JIRA Groups/Teams)
-- =====================================================

CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    group_type VARCHAR(50) DEFAULT 'team', -- team, department, customer, vendor
    parent_group_id UUID REFERENCES groups(id),
    manager_id UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    external_id VARCHAR(255),  -- For syncing with external systems
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

CREATE INDEX idx_groups_org ON groups(organization_id);
CREATE INDEX idx_groups_parent ON groups(parent_group_id);
CREATE INDEX idx_groups_manager ON groups(manager_id);

-- Group membership
CREATE TABLE group_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'member', -- member, lead, admin
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    added_by UUID REFERENCES users(id),
    UNIQUE(group_id, user_id)
);

CREATE INDEX idx_group_members_group ON group_members(group_id);
CREATE INDEX idx_group_members_user ON group_members(user_id);

-- =====================================================
-- CUSTOMERS (External Companies/Contacts)
-- =====================================================

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    short_name VARCHAR(50),
    industry industry_type,
    website VARCHAR(512),
    primary_contact_id UUID,  -- References contacts table
    billing_contact_id UUID,
    technical_contact_id UUID,
    account_manager_id UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    tier VARCHAR(50), -- enterprise, premium, standard
    contract_start DATE,
    contract_end DATE,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customers_org ON customers(organization_id);
CREATE INDEX idx_customers_account_manager ON customers(account_manager_id);

-- =====================================================
-- CONTACTS (Multi-channel contact info)
-- =====================================================

CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    entity_type VARCHAR(50) NOT NULL,  -- 'user', 'customer', 'ticket', 'project'
    entity_id UUID NOT NULL,
    contact_type contact_type NOT NULL,
    value VARCHAR(255) NOT NULL,
    label VARCHAR(100),  -- e.g., "Work", "Personal", "Emergency"
    is_primary BOOLEAN DEFAULT false,
    is_verified BOOLEAN DEFAULT false,
    verified_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contacts_entity ON contacts(entity_type, entity_id);
CREATE INDEX idx_contacts_type ON contacts(contact_type);
CREATE INDEX idx_contacts_org ON contacts(organization_id);

-- =====================================================
-- REPOSITORIES (Git Repository Tracking)
-- =====================================================

CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    url VARCHAR(512) NOT NULL,
    provider VARCHAR(50) DEFAULT 'github', -- github, gitlab, bitbucket, azure_devops
    owner_user_id UUID REFERENCES users(id),
    owner_group_id UUID REFERENCES groups(id),
    default_branch VARCHAR(100) DEFAULT 'main',
    is_active BOOLEAN DEFAULT true,
    is_private BOOLEAN DEFAULT true,
    description TEXT,
    language VARCHAR(50),
    last_synced_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, url)
);

CREATE INDEX idx_repositories_org ON repositories(organization_id);
CREATE INDEX idx_repositories_owner_user ON repositories(owner_user_id);
CREATE INDEX idx_repositories_owner_group ON repositories(owner_group_id);

-- Repository-Ticket linking (many-to-many)
CREATE TABLE ticket_repositories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES change_tickets(id),
    repository_id UUID NOT NULL REFERENCES repositories(id),
    linked_by UUID NOT NULL REFERENCES users(id),
    link_type VARCHAR(50) DEFAULT 'related', -- related, implements, fixes, affects
    branch_name VARCHAR(255),
    commit_sha VARCHAR(40),
    pr_number INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ticket_id, repository_id)
);

CREATE INDEX idx_ticket_repos_ticket ON ticket_repositories(ticket_id);
CREATE INDEX idx_ticket_repos_repo ON ticket_repositories(repository_id);

-- =====================================================
-- TICKET ACLs (Access Control Lists)
-- =====================================================

CREATE TABLE ticket_acls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES change_tickets(id),
    principal_type VARCHAR(20) NOT NULL,  -- 'user', 'group', 'role'
    principal_id UUID,                     -- user_id or group_id (null for role-based)
    role_name VARCHAR(50),                 -- For role-based: 'admin', 'management', 'legal'
    acl_role ticket_acl_role NOT NULL,
    granted_by UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMPTZ,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES users(id),
    UNIQUE(ticket_id, principal_type, principal_id, role_name)
);

CREATE INDEX idx_ticket_acls_ticket ON ticket_acls(ticket_id);
CREATE INDEX idx_ticket_acls_principal ON ticket_acls(principal_type, principal_id);
CREATE INDEX idx_ticket_acls_role ON ticket_acls(role_name) WHERE role_name IS NOT NULL;

-- =====================================================
-- EMPLOYEE DIRECTORY (Extended User Profiles)
-- =====================================================

CREATE TABLE employee_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) UNIQUE,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    employee_number VARCHAR(50),
    job_title VARCHAR(255),
    department VARCHAR(255),
    manager_id UUID REFERENCES users(id),
    employee_type employee_type DEFAULT 'full_time',
    consulting_company VARCHAR(255),  -- If contractor/consultant
    security_clearance security_clearance DEFAULT 'none',
    clearance_expiry DATE,

    -- Location
    office_location VARCHAR(255),
    building VARCHAR(100),
    floor VARCHAR(20),
    desk VARCHAR(50),
    timezone VARCHAR(50),

    -- Contact numbers
    office_phone VARCHAR(50),
    mobile_phone VARCHAR(50),
    home_phone VARCHAR(50),
    fax VARCHAR(50),

    -- Profile
    profile_picture_url VARCHAR(512),
    bio TEXT,
    skills TEXT[],
    certifications TEXT[],

    -- Availability
    work_schedule JSONB,  -- e.g., {"mon": "9-5", "tue": "9-5", ...}
    out_of_office BOOLEAN DEFAULT false,
    out_of_office_message TEXT,
    out_of_office_until TIMESTAMPTZ,
    delegate_id UUID REFERENCES users(id),

    -- Compliance
    last_security_training DATE,
    last_compliance_training DATE,

    -- Dates
    hire_date DATE,
    termination_date DATE,

    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_employee_profiles_user ON employee_profiles(user_id);
CREATE INDEX idx_employee_profiles_manager ON employee_profiles(manager_id);
CREATE INDEX idx_employee_profiles_org ON employee_profiles(organization_id);
CREATE INDEX idx_employee_profiles_department ON employee_profiles(department);
CREATE INDEX idx_employee_profiles_clearance ON employee_profiles(security_clearance);

-- =====================================================
-- TICKET AUDIT LOG (Extended for SOX Compliance)
-- =====================================================

CREATE TABLE ticket_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES change_tickets(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,  -- view, edit, status_change, comment, acl_change, etc.
    action_category VARCHAR(50) NOT NULL,  -- access, modification, approval, compliance

    -- What changed
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changes JSONB,

    -- Context
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    request_id VARCHAR(255),

    -- Compliance flags
    is_compliance_relevant BOOLEAN DEFAULT false,
    compliance_frameworks compliance_framework[],
    requires_review BOOLEAN DEFAULT false,
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,

    -- Immutable timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ticket_audit_ticket ON ticket_audit_log(ticket_id, created_at DESC);
CREATE INDEX idx_ticket_audit_user ON ticket_audit_log(user_id, created_at DESC);
CREATE INDEX idx_ticket_audit_action ON ticket_audit_log(action);
CREATE INDEX idx_ticket_audit_compliance ON ticket_audit_log(is_compliance_relevant)
    WHERE is_compliance_relevant = true;
CREATE INDEX idx_ticket_audit_review ON ticket_audit_log(requires_review)
    WHERE requires_review = true AND reviewed_at IS NULL;

-- Prevent deletion of audit logs (SOX requirement)
CREATE OR REPLACE FUNCTION prevent_audit_deletion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs cannot be deleted per SOX compliance requirements';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_audit_deletion
    BEFORE DELETE ON ticket_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_deletion();

-- =====================================================
-- FAILED SIGNUP ATTEMPTS (Contact Collection)
-- =====================================================

CREATE TABLE failed_signup_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255),
    ip_address INET NOT NULL,
    attempt_count INTEGER DEFAULT 1,
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Collected contact info (after 5 failures)
    contact_collected BOOLEAN DEFAULT false,
    collected_email VARCHAR(255),
    collected_phone VARCHAR(50),
    collected_discord VARCHAR(255),
    collected_slack VARCHAR(255),
    preferred_contact contact_type,
    contact_message TEXT,

    -- Follow-up
    contacted_at TIMESTAMPTZ,
    contacted_by UUID,
    resolution VARCHAR(255),
    resolved_at TIMESTAMPTZ,

    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_failed_signups_email ON failed_signup_attempts(email);
CREATE INDEX idx_failed_signups_ip ON failed_signup_attempts(ip_address);
CREATE INDEX idx_failed_signups_pending ON failed_signup_attempts(contact_collected, resolved_at)
    WHERE contact_collected = true AND resolved_at IS NULL;

-- =====================================================
-- ALTER CHANGE_TICKETS TABLE (Add JIRA-like fields)
-- =====================================================

ALTER TABLE change_tickets
    ADD COLUMN project_id UUID REFERENCES projects(id),
    ADD COLUMN owning_group_id UUID REFERENCES groups(id),
    ADD COLUMN customer_id UUID REFERENCES customers(id),
    ADD COLUMN parent_ticket_id UUID REFERENCES change_tickets(id),
    ADD COLUMN epic_id UUID REFERENCES change_tickets(id),
    ADD COLUMN story_points INTEGER,
    ADD COLUMN time_estimate_hours DECIMAL(10,2),
    ADD COLUMN time_spent_hours DECIMAL(10,2),
    ADD COLUMN labels TEXT[],
    ADD COLUMN watchers UUID[],
    ADD COLUMN external_reference VARCHAR(255),  -- External ticket ID from other systems
    ADD COLUMN acl_inheritance BOOLEAN DEFAULT true,  -- Inherit ACLs from project
    ADD COLUMN is_confidential BOOLEAN DEFAULT false;

CREATE INDEX idx_tickets_project ON change_tickets(project_id);
CREATE INDEX idx_tickets_group ON change_tickets(owning_group_id);
CREATE INDEX idx_tickets_customer ON change_tickets(customer_id);
CREATE INDEX idx_tickets_parent ON change_tickets(parent_ticket_id);
CREATE INDEX idx_tickets_epic ON change_tickets(epic_id);
CREATE INDEX idx_tickets_labels ON change_tickets USING GIN(labels);
CREATE INDEX idx_tickets_watchers ON change_tickets USING GIN(watchers);

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- User's accessible tickets based on ACLs
CREATE VIEW v_user_accessible_tickets AS
SELECT DISTINCT
    t.*,
    CASE
        WHEN t.created_by = u.id THEN 'owner'
        WHEN t.assigned_to = u.id THEN 'assignee'
        WHEN a.acl_role IS NOT NULL THEN a.acl_role::text
        WHEN ga.acl_role IS NOT NULL THEN ga.acl_role::text
        ELSE 'none'
    END as access_level
FROM change_tickets t
CROSS JOIN users u
LEFT JOIN ticket_acls a ON a.ticket_id = t.id
    AND a.principal_type = 'user'
    AND a.principal_id = u.id
    AND a.revoked_at IS NULL
LEFT JOIN ticket_acls ga ON ga.ticket_id = t.id
    AND ga.principal_type = 'group'
    AND ga.principal_id IN (SELECT group_id FROM group_members WHERE user_id = u.id)
    AND ga.revoked_at IS NULL
WHERE t.deleted_at IS NULL
  AND (
    t.created_by = u.id
    OR t.assigned_to = u.id
    OR a.id IS NOT NULL
    OR ga.id IS NOT NULL
    OR 'admin' = ANY(u.roles)
  );

-- Ticket queue for assignment bot
CREATE VIEW v_ticket_queue AS
SELECT
    t.id,
    t.ticket_number,
    t.title,
    t.priority,
    t.risk_level,
    t.status,
    t.created_at,
    t.created_by,
    t.assigned_to,
    p.project_key,
    p.name as project_name,
    g.name as owning_group_name,
    EXTRACT(EPOCH FROM (NOW() - t.created_at))/3600 as hours_since_created,
    CASE
        WHEN t.assigned_to IS NULL THEN true
        ELSE false
    END as needs_assignment
FROM change_tickets t
LEFT JOIN projects p ON t.project_id = p.id
LEFT JOIN groups g ON t.owning_group_id = g.id
WHERE t.status IN ('submitted', 'in_review', 'update_requested')
  AND t.deleted_at IS NULL
ORDER BY
    CASE t.priority
        WHEN 'emergency' THEN 1
        WHEN 'urgent' THEN 2
        WHEN 'high' THEN 3
        WHEN 'normal' THEN 4
        WHEN 'low' THEN 5
    END,
    t.created_at ASC;

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Check if user has access to ticket
CREATE OR REPLACE FUNCTION check_ticket_access(
    p_user_id UUID,
    p_ticket_id UUID,
    p_required_role ticket_acl_role DEFAULT 'viewer'
) RETURNS BOOLEAN AS $$
DECLARE
    v_has_access BOOLEAN := false;
    v_user_roles TEXT[];
BEGIN
    -- Get user roles
    SELECT roles INTO v_user_roles FROM users WHERE id = p_user_id;

    -- Admins have full access
    IF 'admin' = ANY(v_user_roles) THEN
        RETURN true;
    END IF;

    -- Check if user is owner or assignee
    SELECT true INTO v_has_access
    FROM change_tickets
    WHERE id = p_ticket_id
      AND (created_by = p_user_id OR assigned_to = p_user_id);

    IF v_has_access THEN
        RETURN true;
    END IF;

    -- Check direct user ACL
    SELECT true INTO v_has_access
    FROM ticket_acls
    WHERE ticket_id = p_ticket_id
      AND principal_type = 'user'
      AND principal_id = p_user_id
      AND revoked_at IS NULL
      AND (expires_at IS NULL OR expires_at > NOW());

    IF v_has_access THEN
        RETURN true;
    END IF;

    -- Check group membership ACL
    SELECT true INTO v_has_access
    FROM ticket_acls ta
    JOIN group_members gm ON ta.principal_id = gm.group_id
    WHERE ta.ticket_id = p_ticket_id
      AND ta.principal_type = 'group'
      AND gm.user_id = p_user_id
      AND ta.revoked_at IS NULL
      AND (ta.expires_at IS NULL OR ta.expires_at > NOW());

    IF v_has_access THEN
        RETURN true;
    END IF;

    -- Check role-based ACL
    SELECT true INTO v_has_access
    FROM ticket_acls ta
    WHERE ta.ticket_id = p_ticket_id
      AND ta.principal_type = 'role'
      AND ta.role_name = ANY(v_user_roles)
      AND ta.revoked_at IS NULL
      AND (ta.expires_at IS NULL OR ta.expires_at > NOW());

    RETURN COALESCE(v_has_access, false);
END;
$$ LANGUAGE plpgsql;

-- Log ticket access for SOX compliance
CREATE OR REPLACE FUNCTION log_ticket_access(
    p_ticket_id UUID,
    p_user_id UUID,
    p_action VARCHAR,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_changes JSONB DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_org_id UUID;
    v_audit_id UUID;
    v_compliance_frameworks compliance_framework[];
BEGIN
    -- Get organization and compliance info
    SELECT organization_id, compliance_frameworks
    INTO v_org_id, v_compliance_frameworks
    FROM change_tickets
    WHERE id = p_ticket_id;

    -- Insert audit log
    INSERT INTO ticket_audit_log (
        ticket_id,
        organization_id,
        user_id,
        action,
        action_category,
        changes,
        ip_address,
        user_agent,
        is_compliance_relevant,
        compliance_frameworks
    ) VALUES (
        p_ticket_id,
        v_org_id,
        p_user_id,
        p_action,
        CASE
            WHEN p_action IN ('view', 'search', 'export') THEN 'access'
            WHEN p_action IN ('create', 'update', 'delete') THEN 'modification'
            WHEN p_action IN ('approve', 'deny', 'submit') THEN 'approval'
            ELSE 'other'
        END,
        p_changes,
        p_ip_address,
        p_user_agent,
        p_action IN ('create', 'update', 'delete', 'approve', 'deny', 'submit', 'status_change'),
        v_compliance_frameworks
    ) RETURNING id INTO v_audit_id;

    RETURN v_audit_id;
END;
$$ LANGUAGE plpgsql;

-- Track failed signup attempts
CREATE OR REPLACE FUNCTION track_failed_signup(
    p_email VARCHAR,
    p_ip INET
) RETURNS INTEGER AS $$
DECLARE
    v_attempt_count INTEGER;
BEGIN
    INSERT INTO failed_signup_attempts (email, ip_address, attempt_count, last_attempt_at)
    VALUES (p_email, p_ip, 1, NOW())
    ON CONFLICT (email) DO UPDATE
    SET attempt_count = failed_signup_attempts.attempt_count + 1,
        last_attempt_at = NOW()
    RETURNING attempt_count INTO v_attempt_count;

    RETURN v_attempt_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- AUTO-UPDATE TIMESTAMPS
-- =====================================================

CREATE TRIGGER update_projects_timestamp
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_groups_timestamp
    BEFORE UPDATE ON groups
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_customers_timestamp
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_contacts_timestamp
    BEFORE UPDATE ON contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_repositories_timestamp
    BEFORE UPDATE ON repositories
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_employee_profiles_timestamp
    BEFORE UPDATE ON employee_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_failed_signups_timestamp
    BEFORE UPDATE ON failed_signup_attempts
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();
