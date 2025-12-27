package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// ContactType represents the type of contact
type ContactType string

const (
	ContactTypeEmail   ContactType = "email"
	ContactTypePhone   ContactType = "phone"
	ContactTypeDiscord ContactType = "discord"
	ContactTypeSlack   ContactType = "slack"
	ContactTypeTeams   ContactType = "teams"
	ContactTypeFax     ContactType = "fax"
)

// Valid returns true if the contact type is valid
func (c ContactType) Valid() bool {
	switch c {
	case ContactTypeEmail, ContactTypePhone, ContactTypeDiscord, ContactTypeSlack, ContactTypeTeams, ContactTypeFax:
		return true
	}
	return false
}

// Contact represents a contact method for an entity
type Contact struct {
	ID             uuid.UUID       `db:"id" json:"id"`
	OrganizationID uuid.UUID       `db:"organization_id" json:"organization_id"`
	EntityType     string          `db:"entity_type" json:"entity_type"` // user, customer, ticket, project
	EntityID       uuid.UUID       `db:"entity_id" json:"entity_id"`
	ContactType    ContactType     `db:"contact_type" json:"contact_type"`
	Value          string          `db:"value" json:"value"`
	Label          *string         `db:"label" json:"label,omitempty"` // Work, Personal, Emergency
	IsPrimary      bool            `db:"is_primary" json:"is_primary"`
	IsVerified     bool            `db:"is_verified" json:"is_verified"`
	VerifiedAt     *time.Time      `db:"verified_at" json:"verified_at,omitempty"`
	Metadata       json.RawMessage `db:"metadata" json:"metadata,omitempty"`
	CreatedAt      time.Time       `db:"created_at" json:"created_at"`
	UpdatedAt      time.Time       `db:"updated_at" json:"updated_at"`
}

// CreateContactInput represents input for creating a contact
type CreateContactInput struct {
	EntityType  string      `json:"entity_type" validate:"required,oneof=user customer ticket project"`
	EntityID    uuid.UUID   `json:"entity_id" validate:"required"`
	ContactType ContactType `json:"contact_type" validate:"required"`
	Value       string      `json:"value" validate:"required,min=1,max=255"`
	Label       *string     `json:"label,omitempty" validate:"omitempty,max=100"`
	IsPrimary   bool        `json:"is_primary"`
}

// UpdateContactInput represents input for updating a contact
type UpdateContactInput struct {
	ContactType *ContactType `json:"contact_type,omitempty"`
	Value       *string      `json:"value,omitempty" validate:"omitempty,min=1,max=255"`
	Label       *string      `json:"label,omitempty" validate:"omitempty,max=100"`
	IsPrimary   *bool        `json:"is_primary,omitempty"`
}

// Customer represents an external company/customer
type Customer struct {
	ID                 uuid.UUID       `db:"id" json:"id"`
	OrganizationID     uuid.UUID       `db:"organization_id" json:"organization_id"`
	Name               string          `db:"name" json:"name"`
	ShortName          *string         `db:"short_name" json:"short_name,omitempty"`
	Industry           *IndustryType   `db:"industry" json:"industry,omitempty"`
	Website            *string         `db:"website" json:"website,omitempty"`
	PrimaryContactID   *uuid.UUID      `db:"primary_contact_id" json:"primary_contact_id,omitempty"`
	BillingContactID   *uuid.UUID      `db:"billing_contact_id" json:"billing_contact_id,omitempty"`
	TechnicalContactID *uuid.UUID      `db:"technical_contact_id" json:"technical_contact_id,omitempty"`
	AccountManagerID   *uuid.UUID      `db:"account_manager_id" json:"account_manager_id,omitempty"`
	IsActive           bool            `db:"is_active" json:"is_active"`
	Tier               *string         `db:"tier" json:"tier,omitempty"` // enterprise, premium, standard
	ContractStart      *time.Time      `db:"contract_start" json:"contract_start,omitempty"`
	ContractEnd        *time.Time      `db:"contract_end" json:"contract_end,omitempty"`
	Notes              *string         `db:"notes" json:"notes,omitempty"`
	Metadata           json.RawMessage `db:"metadata" json:"metadata,omitempty"`
	CreatedAt          time.Time       `db:"created_at" json:"created_at"`
	UpdatedAt          time.Time       `db:"updated_at" json:"updated_at"`

	// Relationships
	PrimaryContact   *Contact     `db:"-" json:"primary_contact,omitempty"`
	BillingContact   *Contact     `db:"-" json:"billing_contact,omitempty"`
	TechnicalContact *Contact     `db:"-" json:"technical_contact,omitempty"`
	AccountManager   *UserSummary `db:"-" json:"account_manager,omitempty"`
	Contacts         []Contact    `db:"-" json:"contacts,omitempty"`
}

// CustomerSummary is a minimal customer representation
type CustomerSummary struct {
	ID        uuid.UUID `json:"id"`
	Name      string    `json:"name"`
	ShortName *string   `json:"short_name,omitempty"`
	Tier      *string   `json:"tier,omitempty"`
	IsActive  bool      `json:"is_active"`
}

// ToSummary converts Customer to CustomerSummary
func (c *Customer) ToSummary() CustomerSummary {
	return CustomerSummary{
		ID:        c.ID,
		Name:      c.Name,
		ShortName: c.ShortName,
		Tier:      c.Tier,
		IsActive:  c.IsActive,
	}
}

// CreateCustomerInput represents input for creating a customer
type CreateCustomerInput struct {
	Name             string        `json:"name" validate:"required,min=2,max=255"`
	ShortName        *string       `json:"short_name,omitempty" validate:"omitempty,max=50"`
	Industry         *IndustryType `json:"industry,omitempty"`
	Website          *string       `json:"website,omitempty" validate:"omitempty,url"`
	AccountManagerID *uuid.UUID    `json:"account_manager_id,omitempty"`
	Tier             *string       `json:"tier,omitempty" validate:"omitempty,oneof=enterprise premium standard"`
	ContractStart    *time.Time    `json:"contract_start,omitempty"`
	ContractEnd      *time.Time    `json:"contract_end,omitempty"`
	Notes            *string       `json:"notes,omitempty"`
}

// UpdateCustomerInput represents input for updating a customer
type UpdateCustomerInput struct {
	Name             *string       `json:"name,omitempty" validate:"omitempty,min=2,max=255"`
	ShortName        *string       `json:"short_name,omitempty" validate:"omitempty,max=50"`
	Industry         *IndustryType `json:"industry,omitempty"`
	Website          *string       `json:"website,omitempty" validate:"omitempty,url"`
	AccountManagerID *uuid.UUID    `json:"account_manager_id,omitempty"`
	IsActive         *bool         `json:"is_active,omitempty"`
	Tier             *string       `json:"tier,omitempty" validate:"omitempty,oneof=enterprise premium standard"`
	ContractStart    *time.Time    `json:"contract_start,omitempty"`
	ContractEnd      *time.Time    `json:"contract_end,omitempty"`
	Notes            *string       `json:"notes,omitempty"`
}
