package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// GroupType represents the type of group
type GroupType string

const (
	GroupTypeTeam       GroupType = "team"
	GroupTypeDepartment GroupType = "department"
	GroupTypeCustomer   GroupType = "customer"
	GroupTypeVendor     GroupType = "vendor"
)

// Valid returns true if the group type is valid
func (g GroupType) Valid() bool {
	switch g {
	case GroupTypeTeam, GroupTypeDepartment, GroupTypeCustomer, GroupTypeVendor:
		return true
	}
	return false
}

// Group represents a team, department, or organizational unit
type Group struct {
	ID             uuid.UUID       `db:"id" json:"id"`
	OrganizationID uuid.UUID       `db:"organization_id" json:"organization_id"`
	Name           string          `db:"name" json:"name"`
	Description    *string         `db:"description" json:"description,omitempty"`
	GroupType      GroupType       `db:"group_type" json:"group_type"`
	ParentGroupID  *uuid.UUID      `db:"parent_group_id" json:"parent_group_id,omitempty"`
	ManagerID      *uuid.UUID      `db:"manager_id" json:"manager_id,omitempty"`
	IsActive       bool            `db:"is_active" json:"is_active"`
	ExternalID     *string         `db:"external_id" json:"external_id,omitempty"`
	Metadata       json.RawMessage `db:"metadata" json:"metadata,omitempty"`
	CreatedAt      time.Time       `db:"created_at" json:"created_at"`
	UpdatedAt      time.Time       `db:"updated_at" json:"updated_at"`

	// Relationships
	Manager     *UserSummary   `db:"-" json:"manager,omitempty"`
	ParentGroup *GroupSummary  `db:"-" json:"parent_group,omitempty"`
	Members     []GroupMember  `db:"-" json:"members,omitempty"`
	MemberCount int            `db:"-" json:"member_count,omitempty"`
}

// GroupSummary is a minimal group representation
type GroupSummary struct {
	ID        uuid.UUID `json:"id"`
	Name      string    `json:"name"`
	GroupType GroupType `json:"group_type"`
	IsActive  bool      `json:"is_active"`
}

// ToSummary converts Group to GroupSummary
func (g *Group) ToSummary() GroupSummary {
	return GroupSummary{
		ID:        g.ID,
		Name:      g.Name,
		GroupType: g.GroupType,
		IsActive:  g.IsActive,
	}
}

// GroupMember represents a user's membership in a group
type GroupMember struct {
	ID       uuid.UUID    `db:"id" json:"id"`
	GroupID  uuid.UUID    `db:"group_id" json:"group_id"`
	UserID   uuid.UUID    `db:"user_id" json:"user_id"`
	Role     string       `db:"role" json:"role"` // member, lead, admin
	JoinedAt time.Time    `db:"joined_at" json:"joined_at"`
	AddedBy  *uuid.UUID   `db:"added_by" json:"added_by,omitempty"`

	// Relationships
	User *UserSummary `db:"-" json:"user,omitempty"`
}

// CreateGroupInput represents input for creating a group
type CreateGroupInput struct {
	Name          string     `json:"name" validate:"required,min=2,max=255"`
	Description   *string    `json:"description,omitempty"`
	GroupType     GroupType  `json:"group_type" validate:"required"`
	ParentGroupID *uuid.UUID `json:"parent_group_id,omitempty"`
	ManagerID     *uuid.UUID `json:"manager_id,omitempty"`
	ExternalID    *string    `json:"external_id,omitempty"`
}

// UpdateGroupInput represents input for updating a group
type UpdateGroupInput struct {
	Name          *string    `json:"name,omitempty" validate:"omitempty,min=2,max=255"`
	Description   *string    `json:"description,omitempty"`
	GroupType     *GroupType `json:"group_type,omitempty"`
	ParentGroupID *uuid.UUID `json:"parent_group_id,omitempty"`
	ManagerID     *uuid.UUID `json:"manager_id,omitempty"`
	IsActive      *bool      `json:"is_active,omitempty"`
	ExternalID    *string    `json:"external_id,omitempty"`
}

// AddGroupMemberInput represents input for adding a member to a group
type AddGroupMemberInput struct {
	UserID uuid.UUID `json:"user_id" validate:"required"`
	Role   string    `json:"role" validate:"omitempty,oneof=member lead admin"`
}
