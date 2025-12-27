package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// Project represents a JIRA-like project for organizing tickets
type Project struct {
	ID                uuid.UUID       `db:"id" json:"id"`
	OrganizationID    uuid.UUID       `db:"organization_id" json:"organization_id"`
	ProjectKey        string          `db:"project_key" json:"project_key"`
	Name              string          `db:"name" json:"name"`
	Description       *string         `db:"description" json:"description,omitempty"`
	LeadUserID        *uuid.UUID      `db:"lead_user_id" json:"lead_user_id,omitempty"`
	DefaultAssigneeID *uuid.UUID      `db:"default_assignee_id" json:"default_assignee_id,omitempty"`
	OwningGroupID     *uuid.UUID      `db:"owning_group_id" json:"owning_group_id,omitempty"`
	CustomerID        *uuid.UUID      `db:"customer_id" json:"customer_id,omitempty"`
	IsActive          bool            `db:"is_active" json:"is_active"`
	IconURL           *string         `db:"icon_url" json:"icon_url,omitempty"`
	Metadata          json.RawMessage `db:"metadata" json:"metadata,omitempty"`
	CreatedAt         time.Time       `db:"created_at" json:"created_at"`
	UpdatedAt         time.Time       `db:"updated_at" json:"updated_at"`
	CreatedBy         *uuid.UUID      `db:"created_by" json:"created_by,omitempty"`

	// Relationships
	Lead            *UserSummary `db:"-" json:"lead,omitempty"`
	DefaultAssignee *UserSummary `db:"-" json:"default_assignee,omitempty"`
	OwningGroup     *Group       `db:"-" json:"owning_group,omitempty"`
	Customer        *Customer    `db:"-" json:"customer,omitempty"`
}

// ProjectSummary is a minimal project representation
type ProjectSummary struct {
	ID         uuid.UUID `json:"id"`
	ProjectKey string    `json:"project_key"`
	Name       string    `json:"name"`
	IsActive   bool      `json:"is_active"`
}

// ToSummary converts Project to ProjectSummary
func (p *Project) ToSummary() ProjectSummary {
	return ProjectSummary{
		ID:         p.ID,
		ProjectKey: p.ProjectKey,
		Name:       p.Name,
		IsActive:   p.IsActive,
	}
}

// CreateProjectInput represents input for creating a project
type CreateProjectInput struct {
	ProjectKey        string     `json:"project_key" validate:"required,min=2,max=10,alphanum,uppercase"`
	Name              string     `json:"name" validate:"required,min=2,max=255"`
	Description       *string    `json:"description,omitempty"`
	LeadUserID        *uuid.UUID `json:"lead_user_id,omitempty"`
	DefaultAssigneeID *uuid.UUID `json:"default_assignee_id,omitempty"`
	OwningGroupID     *uuid.UUID `json:"owning_group_id,omitempty"`
	CustomerID        *uuid.UUID `json:"customer_id,omitempty"`
	IconURL           *string    `json:"icon_url,omitempty"`
}

// UpdateProjectInput represents input for updating a project
type UpdateProjectInput struct {
	Name              *string    `json:"name,omitempty" validate:"omitempty,min=2,max=255"`
	Description       *string    `json:"description,omitempty"`
	LeadUserID        *uuid.UUID `json:"lead_user_id,omitempty"`
	DefaultAssigneeID *uuid.UUID `json:"default_assignee_id,omitempty"`
	OwningGroupID     *uuid.UUID `json:"owning_group_id,omitempty"`
	CustomerID        *uuid.UUID `json:"customer_id,omitempty"`
	IsActive          *bool      `json:"is_active,omitempty"`
	IconURL           *string    `json:"icon_url,omitempty"`
}
