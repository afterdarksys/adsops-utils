package models

import (
	"time"

	"github.com/google/uuid"
)

// AgentType distinguishes agent subtypes
type AgentType string

const (
	AgentTypeAgent   AgentType = "agent"
	AgentTypeService AgentType = "service"
)

// Valid returns true if the agent type is valid
func (a AgentType) Valid() bool {
	switch a {
	case AgentTypeAgent, AgentTypeService:
		return true
	}
	return false
}

// AgentRole defines authorization level for agents
type AgentRole string

const (
	AgentRoleViewer   AgentRole = "viewer"
	AgentRoleOperator AgentRole = "operator"
	AgentRoleApprover AgentRole = "approver"
	AgentRoleAdmin    AgentRole = "admin"
)

// Valid returns true if the agent role is valid
func (r AgentRole) Valid() bool {
	switch r {
	case AgentRoleViewer, AgentRoleOperator, AgentRoleApprover, AgentRoleAdmin:
		return true
	}
	return false
}

// Agent represents a registered AI agent or service identity
type Agent struct {
	ID           uuid.UUID `db:"id" json:"id"`
	AgentID      string    `db:"agent_id" json:"agent_id"`  // e.g. "kai_nakamura"
	Type         AgentType `db:"type" json:"type"`
	DisplayName  string    `db:"display_name" json:"display_name"`
	Capabilities []string  `db:"capabilities" json:"capabilities"`
	Role         AgentRole `db:"role" json:"role"`
	Active       bool      `db:"active" json:"active"`
	WebhookURL   *string   `db:"webhook_url" json:"webhook_url,omitempty"`
	CreatedAt    time.Time `db:"created_at" json:"created_at"`
	UpdatedAt    time.Time `db:"updated_at" json:"updated_at"`
}

// AgentToken represents a long-lived API token issued to an agent
type AgentToken struct {
	ID          uuid.UUID  `db:"id" json:"id"`
	AgentID     uuid.UUID  `db:"agent_id" json:"agent_id"`
	TokenHash   string     `db:"token_hash" json:"-"` // bcrypt hash — never returned
	Label       string     `db:"label" json:"label"`
	CreatedAt   time.Time  `db:"created_at" json:"created_at"`
	ExpiresAt   *time.Time `db:"expires_at" json:"expires_at,omitempty"`
	LastUsedAt  *time.Time `db:"last_used_at" json:"last_used_at,omitempty"`
	RevokedAt   *time.Time `db:"revoked_at" json:"revoked_at,omitempty"`
}
