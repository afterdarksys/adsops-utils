package models

import (
	"time"

	"github.com/google/uuid"
)

// TicketACLRole represents the role/permission level in a ticket ACL
type TicketACLRole string

const (
	TicketACLRoleViewer     TicketACLRole = "viewer"
	TicketACLRoleCommenter  TicketACLRole = "commenter"
	TicketACLRoleEditor     TicketACLRole = "editor"
	TicketACLRoleOwner      TicketACLRole = "owner"
	TicketACLRoleAdmin      TicketACLRole = "admin"
	TicketACLRoleManagement TicketACLRole = "management"
	TicketACLRoleLegal      TicketACLRole = "legal"
	TicketACLRoleAuditor    TicketACLRole = "auditor"
)

// Valid returns true if the ACL role is valid
func (t TicketACLRole) Valid() bool {
	switch t {
	case TicketACLRoleViewer, TicketACLRoleCommenter, TicketACLRoleEditor, TicketACLRoleOwner,
		TicketACLRoleAdmin, TicketACLRoleManagement, TicketACLRoleLegal, TicketACLRoleAuditor:
		return true
	}
	return false
}

// CanView returns true if the role can view tickets
func (t TicketACLRole) CanView() bool {
	return t.Valid() // All valid roles can view
}

// CanComment returns true if the role can add comments
func (t TicketACLRole) CanComment() bool {
	switch t {
	case TicketACLRoleCommenter, TicketACLRoleEditor, TicketACLRoleOwner, TicketACLRoleAdmin, TicketACLRoleManagement:
		return true
	}
	return false
}

// CanEdit returns true if the role can edit tickets
func (t TicketACLRole) CanEdit() bool {
	switch t {
	case TicketACLRoleEditor, TicketACLRoleOwner, TicketACLRoleAdmin:
		return true
	}
	return false
}

// CanManageACLs returns true if the role can manage ticket ACLs
func (t TicketACLRole) CanManageACLs() bool {
	switch t {
	case TicketACLRoleOwner, TicketACLRoleAdmin:
		return true
	}
	return false
}

// DisplayName returns a human-readable name for the role
func (t TicketACLRole) DisplayName() string {
	switch t {
	case TicketACLRoleViewer:
		return "Viewer"
	case TicketACLRoleCommenter:
		return "Commenter"
	case TicketACLRoleEditor:
		return "Editor"
	case TicketACLRoleOwner:
		return "Owner"
	case TicketACLRoleAdmin:
		return "Administrator"
	case TicketACLRoleManagement:
		return "Management"
	case TicketACLRoleLegal:
		return "Legal"
	case TicketACLRoleAuditor:
		return "Auditor"
	}
	return string(t)
}

// TicketACL represents an access control entry for a ticket
type TicketACL struct {
	ID            uuid.UUID     `db:"id" json:"id"`
	TicketID      uuid.UUID     `db:"ticket_id" json:"ticket_id"`
	PrincipalType string        `db:"principal_type" json:"principal_type"` // user, group, role
	PrincipalID   *uuid.UUID    `db:"principal_id" json:"principal_id,omitempty"`
	RoleName      *string       `db:"role_name" json:"role_name,omitempty"` // For role-based ACLs
	ACLRole       TicketACLRole `db:"acl_role" json:"acl_role"`
	GrantedBy     uuid.UUID     `db:"granted_by" json:"granted_by"`
	ExpiresAt     *time.Time    `db:"expires_at" json:"expires_at,omitempty"`
	Reason        *string       `db:"reason" json:"reason,omitempty"`
	CreatedAt     time.Time     `db:"created_at" json:"created_at"`
	RevokedAt     *time.Time    `db:"revoked_at" json:"revoked_at,omitempty"`
	RevokedBy     *uuid.UUID    `db:"revoked_by" json:"revoked_by,omitempty"`

	// Relationships
	GrantedByUser *UserSummary  `db:"-" json:"granted_by_user,omitempty"`
	RevokedByUser *UserSummary  `db:"-" json:"revoked_by_user,omitempty"`
	Principal     *UserSummary  `db:"-" json:"principal,omitempty"`      // If principal_type is user
	PrincipalGroup *GroupSummary `db:"-" json:"principal_group,omitempty"` // If principal_type is group
}

// IsActive returns true if the ACL is currently active
func (a *TicketACL) IsActive() bool {
	if a.RevokedAt != nil {
		return false
	}
	if a.ExpiresAt != nil && a.ExpiresAt.Before(time.Now()) {
		return false
	}
	return true
}

// GrantTicketACLInput represents input for granting access to a ticket
type GrantTicketACLInput struct {
	TicketID      uuid.UUID     `json:"ticket_id" validate:"required"`
	PrincipalType string        `json:"principal_type" validate:"required,oneof=user group role"`
	PrincipalID   *uuid.UUID    `json:"principal_id,omitempty"`   // Required for user/group
	RoleName      *string       `json:"role_name,omitempty"`      // Required for role
	ACLRole       TicketACLRole `json:"acl_role" validate:"required"`
	ExpiresAt     *time.Time    `json:"expires_at,omitempty"`
	Reason        *string       `json:"reason,omitempty"`
}

// Validate validates the input
func (i *GrantTicketACLInput) Validate() error {
	if i.PrincipalType == "user" || i.PrincipalType == "group" {
		if i.PrincipalID == nil {
			return &ValidationError{Field: "principal_id", Message: "principal_id is required for user/group type"}
		}
	}
	if i.PrincipalType == "role" {
		if i.RoleName == nil || *i.RoleName == "" {
			return &ValidationError{Field: "role_name", Message: "role_name is required for role type"}
		}
	}
	return nil
}

// RevokeTicketACLInput represents input for revoking access to a ticket
type RevokeTicketACLInput struct {
	ACLID  uuid.UUID `json:"acl_id" validate:"required"`
	Reason *string   `json:"reason,omitempty"`
}

// BulkGrantACLInput represents input for bulk granting ACLs
type BulkGrantACLInput struct {
	TicketID  uuid.UUID      `json:"ticket_id" validate:"required"`
	UserIDs   []uuid.UUID    `json:"user_ids,omitempty"`
	GroupIDs  []uuid.UUID    `json:"group_ids,omitempty"`
	RoleNames []string       `json:"role_names,omitempty"`
	ACLRole   TicketACLRole  `json:"acl_role" validate:"required"`
	ExpiresAt *time.Time     `json:"expires_at,omitempty"`
	Reason    *string        `json:"reason,omitempty"`
}

// TicketAuditLog represents a SOX-compliant audit log entry for tickets
type TicketAuditLog struct {
	ID                   uuid.UUID             `db:"id" json:"id"`
	TicketID             uuid.UUID             `db:"ticket_id" json:"ticket_id"`
	OrganizationID       uuid.UUID             `db:"organization_id" json:"organization_id"`
	UserID               *uuid.UUID            `db:"user_id" json:"user_id,omitempty"`
	Action               string                `db:"action" json:"action"`
	ActionCategory       string                `db:"action_category" json:"action_category"` // access, modification, approval, compliance
	FieldName            *string               `db:"field_name" json:"field_name,omitempty"`
	OldValue             *string               `db:"old_value" json:"old_value,omitempty"`
	NewValue             *string               `db:"new_value" json:"new_value,omitempty"`
	Changes              map[string]any        `db:"changes" json:"changes,omitempty"`
	IPAddress            *string               `db:"ip_address" json:"ip_address,omitempty"`
	UserAgent            *string               `db:"user_agent" json:"user_agent,omitempty"`
	SessionID            *string               `db:"session_id" json:"session_id,omitempty"`
	RequestID            *string               `db:"request_id" json:"request_id,omitempty"`
	IsComplianceRelevant bool                  `db:"is_compliance_relevant" json:"is_compliance_relevant"`
	ComplianceFrameworks []ComplianceFramework `db:"compliance_frameworks" json:"compliance_frameworks,omitempty"`
	RequiresReview       bool                  `db:"requires_review" json:"requires_review"`
	ReviewedBy           *uuid.UUID            `db:"reviewed_by" json:"reviewed_by,omitempty"`
	ReviewedAt           *time.Time            `db:"reviewed_at" json:"reviewed_at,omitempty"`
	CreatedAt            time.Time             `db:"created_at" json:"created_at"`

	// Relationships
	User         *UserSummary `db:"-" json:"user,omitempty"`
	ReviewedByUser *UserSummary `db:"-" json:"reviewed_by_user,omitempty"`
}

// AuditLogFilter represents filter options for viewing audit logs
type AuditLogFilter struct {
	TicketID             *uuid.UUID `json:"ticket_id,omitempty"`
	UserID               *uuid.UUID `json:"user_id,omitempty"`
	Action               *string    `json:"action,omitempty"`
	ActionCategory       *string    `json:"action_category,omitempty"`
	IsComplianceRelevant *bool      `json:"is_compliance_relevant,omitempty"`
	RequiresReview       *bool      `json:"requires_review,omitempty"`
	FromDate             *time.Time `json:"from_date,omitempty"`
	ToDate               *time.Time `json:"to_date,omitempty"`
	Page                 int        `json:"page" validate:"min=1"`
	PerPage              int        `json:"per_page" validate:"min=1,max=100"`
}

// SetDefaults sets default values for the filter
func (f *AuditLogFilter) SetDefaults() {
	if f.Page < 1 {
		f.Page = 1
	}
	if f.PerPage < 1 || f.PerPage > 100 {
		f.PerPage = 50
	}
}

// Offset returns the offset for pagination
func (f *AuditLogFilter) Offset() int {
	return (f.Page - 1) * f.PerPage
}

// ValidationError represents a validation error
type ValidationError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
}

func (e *ValidationError) Error() string {
	return e.Field + ": " + e.Message
}

// FailedSignupAttempt represents a failed signup attempt with contact info
type FailedSignupAttempt struct {
	ID                uuid.UUID    `db:"id" json:"id"`
	Email             *string      `db:"email" json:"email,omitempty"`
	IPAddress         string       `db:"ip_address" json:"ip_address"`
	AttemptCount      int          `db:"attempt_count" json:"attempt_count"`
	LastAttemptAt     time.Time    `db:"last_attempt_at" json:"last_attempt_at"`
	FirstAttemptAt    time.Time    `db:"first_attempt_at" json:"first_attempt_at"`
	ContactCollected  bool         `db:"contact_collected" json:"contact_collected"`
	CollectedEmail    *string      `db:"collected_email" json:"collected_email,omitempty"`
	CollectedPhone    *string      `db:"collected_phone" json:"collected_phone,omitempty"`
	CollectedDiscord  *string      `db:"collected_discord" json:"collected_discord,omitempty"`
	CollectedSlack    *string      `db:"collected_slack" json:"collected_slack,omitempty"`
	PreferredContact  *ContactType `db:"preferred_contact" json:"preferred_contact,omitempty"`
	ContactMessage    *string      `db:"contact_message" json:"contact_message,omitempty"`
	ContactedAt       *time.Time   `db:"contacted_at" json:"contacted_at,omitempty"`
	ContactedBy       *uuid.UUID   `db:"contacted_by" json:"contacted_by,omitempty"`
	Resolution        *string      `db:"resolution" json:"resolution,omitempty"`
	ResolvedAt        *time.Time   `db:"resolved_at" json:"resolved_at,omitempty"`
	CreatedAt         time.Time    `db:"created_at" json:"created_at"`
	UpdatedAt         time.Time    `db:"updated_at" json:"updated_at"`
}

// CollectContactInfoInput represents input for collecting contact info after failed signups
type CollectContactInfoInput struct {
	Email            string       `json:"email" validate:"required,email"`
	Phone            *string      `json:"phone,omitempty"`
	Discord          *string      `json:"discord,omitempty"`
	Slack            *string      `json:"slack,omitempty"`
	PreferredContact *ContactType `json:"preferred_contact,omitempty"`
	Message          *string      `json:"message,omitempty"`
}

// ResolveFailedSignupInput represents input for resolving a failed signup
type ResolveFailedSignupInput struct {
	Resolution string `json:"resolution" validate:"required"`
}
