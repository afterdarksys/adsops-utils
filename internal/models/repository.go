package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// RepositoryProvider represents the git hosting provider
type RepositoryProvider string

const (
	RepositoryProviderGitHub      RepositoryProvider = "github"
	RepositoryProviderGitLab      RepositoryProvider = "gitlab"
	RepositoryProviderBitbucket   RepositoryProvider = "bitbucket"
	RepositoryProviderAzureDevOps RepositoryProvider = "azure_devops"
)

// Valid returns true if the provider is valid
func (r RepositoryProvider) Valid() bool {
	switch r {
	case RepositoryProviderGitHub, RepositoryProviderGitLab, RepositoryProviderBitbucket, RepositoryProviderAzureDevOps:
		return true
	}
	return false
}

// Repository represents a git repository
type Repository struct {
	ID             uuid.UUID          `db:"id" json:"id"`
	OrganizationID uuid.UUID          `db:"organization_id" json:"organization_id"`
	Name           string             `db:"name" json:"name"`
	URL            string             `db:"url" json:"url"`
	Provider       RepositoryProvider `db:"provider" json:"provider"`
	OwnerUserID    *uuid.UUID         `db:"owner_user_id" json:"owner_user_id,omitempty"`
	OwnerGroupID   *uuid.UUID         `db:"owner_group_id" json:"owner_group_id,omitempty"`
	DefaultBranch  string             `db:"default_branch" json:"default_branch"`
	IsActive       bool               `db:"is_active" json:"is_active"`
	IsPrivate      bool               `db:"is_private" json:"is_private"`
	Description    *string            `db:"description" json:"description,omitempty"`
	Language       *string            `db:"language" json:"language,omitempty"`
	LastSyncedAt   *time.Time         `db:"last_synced_at" json:"last_synced_at,omitempty"`
	Metadata       json.RawMessage    `db:"metadata" json:"metadata,omitempty"`
	CreatedAt      time.Time          `db:"created_at" json:"created_at"`
	UpdatedAt      time.Time          `db:"updated_at" json:"updated_at"`

	// Relationships
	OwnerUser  *UserSummary  `db:"-" json:"owner_user,omitempty"`
	OwnerGroup *GroupSummary `db:"-" json:"owner_group,omitempty"`
}

// RepositorySummary is a minimal repository representation
type RepositorySummary struct {
	ID       uuid.UUID          `json:"id"`
	Name     string             `json:"name"`
	URL      string             `json:"url"`
	Provider RepositoryProvider `json:"provider"`
	IsActive bool               `json:"is_active"`
}

// ToSummary converts Repository to RepositorySummary
func (r *Repository) ToSummary() RepositorySummary {
	return RepositorySummary{
		ID:       r.ID,
		Name:     r.Name,
		URL:      r.URL,
		Provider: r.Provider,
		IsActive: r.IsActive,
	}
}

// TicketRepository represents a link between a ticket and a repository
type TicketRepository struct {
	ID           uuid.UUID  `db:"id" json:"id"`
	TicketID     uuid.UUID  `db:"ticket_id" json:"ticket_id"`
	RepositoryID uuid.UUID  `db:"repository_id" json:"repository_id"`
	LinkedBy     uuid.UUID  `db:"linked_by" json:"linked_by"`
	LinkType     string     `db:"link_type" json:"link_type"` // related, implements, fixes, affects
	BranchName   *string    `db:"branch_name" json:"branch_name,omitempty"`
	CommitSHA    *string    `db:"commit_sha" json:"commit_sha,omitempty"`
	PRNumber     *int       `db:"pr_number" json:"pr_number,omitempty"`
	Notes        *string    `db:"notes" json:"notes,omitempty"`
	CreatedAt    time.Time  `db:"created_at" json:"created_at"`

	// Relationships
	Repository *RepositorySummary `db:"-" json:"repository,omitempty"`
	LinkedByUser *UserSummary     `db:"-" json:"linked_by_user,omitempty"`
}

// CreateRepositoryInput represents input for creating a repository
type CreateRepositoryInput struct {
	Name          string             `json:"name" validate:"required,min=1,max=255"`
	URL           string             `json:"url" validate:"required,url"`
	Provider      RepositoryProvider `json:"provider" validate:"required"`
	OwnerUserID   *uuid.UUID         `json:"owner_user_id,omitempty"`
	OwnerGroupID  *uuid.UUID         `json:"owner_group_id,omitempty"`
	DefaultBranch string             `json:"default_branch" validate:"omitempty,max=100"`
	IsPrivate     *bool              `json:"is_private,omitempty"`
	Description   *string            `json:"description,omitempty"`
	Language      *string            `json:"language,omitempty"`
}

// UpdateRepositoryInput represents input for updating a repository
type UpdateRepositoryInput struct {
	Name          *string            `json:"name,omitempty" validate:"omitempty,min=1,max=255"`
	URL           *string            `json:"url,omitempty" validate:"omitempty,url"`
	Provider      *RepositoryProvider `json:"provider,omitempty"`
	OwnerUserID   *uuid.UUID         `json:"owner_user_id,omitempty"`
	OwnerGroupID  *uuid.UUID         `json:"owner_group_id,omitempty"`
	DefaultBranch *string            `json:"default_branch,omitempty" validate:"omitempty,max=100"`
	IsActive      *bool              `json:"is_active,omitempty"`
	IsPrivate     *bool              `json:"is_private,omitempty"`
	Description   *string            `json:"description,omitempty"`
	Language      *string            `json:"language,omitempty"`
}

// LinkRepositoryInput represents input for linking a repository to a ticket
type LinkRepositoryInput struct {
	RepositoryID uuid.UUID `json:"repository_id" validate:"required"`
	LinkType     string    `json:"link_type" validate:"omitempty,oneof=related implements fixes affects"`
	BranchName   *string   `json:"branch_name,omitempty"`
	CommitSHA    *string   `json:"commit_sha,omitempty"`
	PRNumber     *int      `json:"pr_number,omitempty"`
	Notes        *string   `json:"notes,omitempty"`
}

// LinkRepositoryByURLInput represents input for linking a repository by URL
type LinkRepositoryByURLInput struct {
	URL        string  `json:"url" validate:"required,url"`
	LinkType   string  `json:"link_type" validate:"omitempty,oneof=related implements fixes affects"`
	BranchName *string `json:"branch_name,omitempty"`
	CommitSHA  *string `json:"commit_sha,omitempty"`
	PRNumber   *int    `json:"pr_number,omitempty"`
	Notes      *string `json:"notes,omitempty"`
}

// RepositoryListFilter represents filter options for listing repositories
type RepositoryListFilter struct {
	Provider     *RepositoryProvider `json:"provider,omitempty"`
	OwnerUserID  *uuid.UUID          `json:"owner_user_id,omitempty"`
	OwnerGroupID *uuid.UUID          `json:"owner_group_id,omitempty"`
	IsActive     *bool               `json:"is_active,omitempty"`
	Search       string              `json:"search,omitempty"`
	Page         int                 `json:"page" validate:"min=1"`
	PerPage      int                 `json:"per_page" validate:"min=1,max=100"`
	SortBy       string              `json:"sort_by,omitempty"`
	SortOrder    string              `json:"sort_order,omitempty"`
}

// SetDefaults sets default values for the filter
func (f *RepositoryListFilter) SetDefaults() {
	if f.Page < 1 {
		f.Page = 1
	}
	if f.PerPage < 1 || f.PerPage > 100 {
		f.PerPage = 50
	}
	if f.SortBy == "" {
		f.SortBy = "name"
	}
	if f.SortOrder == "" {
		f.SortOrder = "asc"
	}
}

// Offset returns the offset for pagination
func (f *RepositoryListFilter) Offset() int {
	return (f.Page - 1) * f.PerPage
}
