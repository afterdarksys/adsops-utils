package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// SecurityClearance represents security clearance levels
type SecurityClearance string

const (
	SecurityClearanceNone        SecurityClearance = "none"
	SecurityClearanceConfidential SecurityClearance = "confidential"
	SecurityClearanceSecret      SecurityClearance = "secret"
	SecurityClearanceTopSecret   SecurityClearance = "top_secret"
	SecurityClearanceTSSCI       SecurityClearance = "ts_sci"
)

// Valid returns true if the clearance is valid
func (s SecurityClearance) Valid() bool {
	switch s {
	case SecurityClearanceNone, SecurityClearanceConfidential, SecurityClearanceSecret, SecurityClearanceTopSecret, SecurityClearanceTSSCI:
		return true
	}
	return false
}

// DisplayName returns a human-readable name for the clearance
func (s SecurityClearance) DisplayName() string {
	switch s {
	case SecurityClearanceNone:
		return "No Clearance"
	case SecurityClearanceConfidential:
		return "Confidential"
	case SecurityClearanceSecret:
		return "Secret"
	case SecurityClearanceTopSecret:
		return "Top Secret"
	case SecurityClearanceTSSCI:
		return "TS/SCI"
	}
	return string(s)
}

// EmployeeType represents the type of employee
type EmployeeType string

const (
	EmployeeTypeFullTime   EmployeeType = "full_time"
	EmployeeTypeContractor EmployeeType = "contractor"
	EmployeeTypeConsultant EmployeeType = "consultant"
	EmployeeTypeIntern     EmployeeType = "intern"
	EmployeeTypeVendor     EmployeeType = "vendor"
)

// Valid returns true if the employee type is valid
func (e EmployeeType) Valid() bool {
	switch e {
	case EmployeeTypeFullTime, EmployeeTypeContractor, EmployeeTypeConsultant, EmployeeTypeIntern, EmployeeTypeVendor:
		return true
	}
	return false
}

// EmployeeProfile represents extended employee information
type EmployeeProfile struct {
	ID                uuid.UUID         `db:"id" json:"id"`
	UserID            uuid.UUID         `db:"user_id" json:"user_id"`
	OrganizationID    uuid.UUID         `db:"organization_id" json:"organization_id"`
	EmployeeNumber    *string           `db:"employee_number" json:"employee_number,omitempty"`
	JobTitle          *string           `db:"job_title" json:"job_title,omitempty"`
	Department        *string           `db:"department" json:"department,omitempty"`
	ManagerID         *uuid.UUID        `db:"manager_id" json:"manager_id,omitempty"`
	EmployeeType      EmployeeType      `db:"employee_type" json:"employee_type"`
	ConsultingCompany *string           `db:"consulting_company" json:"consulting_company,omitempty"`
	SecurityClearance SecurityClearance `db:"security_clearance" json:"security_clearance"`
	ClearanceExpiry   *time.Time        `db:"clearance_expiry" json:"clearance_expiry,omitempty"`

	// Location
	OfficeLocation *string `db:"office_location" json:"office_location,omitempty"`
	Building       *string `db:"building" json:"building,omitempty"`
	Floor          *string `db:"floor" json:"floor,omitempty"`
	Desk           *string `db:"desk" json:"desk,omitempty"`
	Timezone       *string `db:"timezone" json:"timezone,omitempty"`

	// Contact numbers
	OfficePhone *string `db:"office_phone" json:"office_phone,omitempty"`
	MobilePhone *string `db:"mobile_phone" json:"mobile_phone,omitempty"`
	HomePhone   *string `db:"home_phone" json:"home_phone,omitempty"`
	Fax         *string `db:"fax" json:"fax,omitempty"`

	// Profile
	ProfilePictureURL *string  `db:"profile_picture_url" json:"profile_picture_url,omitempty"`
	Bio               *string  `db:"bio" json:"bio,omitempty"`
	Skills            []string `db:"skills" json:"skills,omitempty"`
	Certifications    []string `db:"certifications" json:"certifications,omitempty"`

	// Availability
	WorkSchedule        json.RawMessage `db:"work_schedule" json:"work_schedule,omitempty"`
	OutOfOffice         bool            `db:"out_of_office" json:"out_of_office"`
	OutOfOfficeMessage  *string         `db:"out_of_office_message" json:"out_of_office_message,omitempty"`
	OutOfOfficeUntil    *time.Time      `db:"out_of_office_until" json:"out_of_office_until,omitempty"`
	DelegateID          *uuid.UUID      `db:"delegate_id" json:"delegate_id,omitempty"`

	// Compliance
	LastSecurityTraining   *time.Time `db:"last_security_training" json:"last_security_training,omitempty"`
	LastComplianceTraining *time.Time `db:"last_compliance_training" json:"last_compliance_training,omitempty"`

	// Dates
	HireDate        *time.Time `db:"hire_date" json:"hire_date,omitempty"`
	TerminationDate *time.Time `db:"termination_date" json:"termination_date,omitempty"`

	Metadata  json.RawMessage `db:"metadata" json:"metadata,omitempty"`
	CreatedAt time.Time       `db:"created_at" json:"created_at"`
	UpdatedAt time.Time       `db:"updated_at" json:"updated_at"`

	// Relationships
	User     *UserSummary `db:"-" json:"user,omitempty"`
	Manager  *UserSummary `db:"-" json:"manager,omitempty"`
	Delegate *UserSummary `db:"-" json:"delegate,omitempty"`
}

// EmployeeDirectoryEntry represents a public-facing employee entry
type EmployeeDirectoryEntry struct {
	ID                uuid.UUID    `json:"id"`
	UserID            uuid.UUID    `json:"user_id"`
	FullName          string       `json:"full_name"`
	Email             string       `json:"email"`
	JobTitle          *string      `json:"job_title,omitempty"`
	Department        *string      `json:"department,omitempty"`
	EmployeeType      EmployeeType `json:"employee_type"`
	ConsultingCompany *string      `json:"consulting_company,omitempty"`
	OfficeLocation    *string      `json:"office_location,omitempty"`
	OfficePhone       *string      `json:"office_phone,omitempty"`
	MobilePhone       *string      `json:"mobile_phone,omitempty"`
	ProfilePictureURL *string      `json:"profile_picture_url,omitempty"`
	OutOfOffice       bool         `json:"out_of_office"`
	Manager           *UserSummary `json:"manager,omitempty"`
}

// EmployeeDetailView represents a detailed employee view (for admin/self)
type EmployeeDetailView struct {
	EmployeeDirectoryEntry
	HomePhone         *string           `json:"home_phone,omitempty"`
	Fax               *string           `json:"fax,omitempty"`
	Building          *string           `json:"building,omitempty"`
	Floor             *string           `json:"floor,omitempty"`
	Desk              *string           `json:"desk,omitempty"`
	Timezone          *string           `json:"timezone,omitempty"`
	SecurityClearance SecurityClearance `json:"security_clearance"` // Only visible to admins or self
	ClearanceExpiry   *time.Time        `json:"clearance_expiry,omitempty"`
	Bio               *string           `json:"bio,omitempty"`
	Skills            []string          `json:"skills,omitempty"`
	Certifications    []string          `json:"certifications,omitempty"`
	HireDate          *time.Time        `json:"hire_date,omitempty"`
}

// CreateEmployeeProfileInput represents input for creating an employee profile
type CreateEmployeeProfileInput struct {
	UserID            uuid.UUID         `json:"user_id" validate:"required"`
	EmployeeNumber    *string           `json:"employee_number,omitempty"`
	JobTitle          *string           `json:"job_title,omitempty"`
	Department        *string           `json:"department,omitempty"`
	ManagerID         *uuid.UUID        `json:"manager_id,omitempty"`
	EmployeeType      EmployeeType      `json:"employee_type" validate:"required"`
	ConsultingCompany *string           `json:"consulting_company,omitempty"`
	SecurityClearance SecurityClearance `json:"security_clearance"`
	ClearanceExpiry   *time.Time        `json:"clearance_expiry,omitempty"`
	OfficeLocation    *string           `json:"office_location,omitempty"`
	Building          *string           `json:"building,omitempty"`
	Floor             *string           `json:"floor,omitempty"`
	Desk              *string           `json:"desk,omitempty"`
	Timezone          *string           `json:"timezone,omitempty"`
	OfficePhone       *string           `json:"office_phone,omitempty"`
	MobilePhone       *string           `json:"mobile_phone,omitempty"`
	HomePhone         *string           `json:"home_phone,omitempty"`
	Fax               *string           `json:"fax,omitempty"`
	ProfilePictureURL *string           `json:"profile_picture_url,omitempty"`
	Bio               *string           `json:"bio,omitempty"`
	Skills            []string          `json:"skills,omitempty"`
	Certifications    []string          `json:"certifications,omitempty"`
	HireDate          *time.Time        `json:"hire_date,omitempty"`
}

// UpdateEmployeeProfileInput represents input for updating an employee profile
type UpdateEmployeeProfileInput struct {
	EmployeeNumber    *string            `json:"employee_number,omitempty"`
	JobTitle          *string            `json:"job_title,omitempty"`
	Department        *string            `json:"department,omitempty"`
	ManagerID         *uuid.UUID         `json:"manager_id,omitempty"`
	EmployeeType      *EmployeeType      `json:"employee_type,omitempty"`
	ConsultingCompany *string            `json:"consulting_company,omitempty"`
	SecurityClearance *SecurityClearance `json:"security_clearance,omitempty"`
	ClearanceExpiry   *time.Time         `json:"clearance_expiry,omitempty"`
	OfficeLocation    *string            `json:"office_location,omitempty"`
	Building          *string            `json:"building,omitempty"`
	Floor             *string            `json:"floor,omitempty"`
	Desk              *string            `json:"desk,omitempty"`
	Timezone          *string            `json:"timezone,omitempty"`
	OfficePhone       *string            `json:"office_phone,omitempty"`
	MobilePhone       *string            `json:"mobile_phone,omitempty"`
	HomePhone         *string            `json:"home_phone,omitempty"`
	Fax               *string            `json:"fax,omitempty"`
	ProfilePictureURL *string            `json:"profile_picture_url,omitempty"`
	Bio               *string            `json:"bio,omitempty"`
	Skills            []string           `json:"skills,omitempty"`
	Certifications    []string           `json:"certifications,omitempty"`
	OutOfOffice       *bool              `json:"out_of_office,omitempty"`
	OutOfOfficeMessage *string           `json:"out_of_office_message,omitempty"`
	OutOfOfficeUntil  *time.Time         `json:"out_of_office_until,omitempty"`
	DelegateID        *uuid.UUID         `json:"delegate_id,omitempty"`
	HireDate          *time.Time         `json:"hire_date,omitempty"`
	TerminationDate   *time.Time         `json:"termination_date,omitempty"`
}

// EmployeeSearchFilter represents filter options for searching employees
type EmployeeSearchFilter struct {
	Department        *string        `json:"department,omitempty"`
	EmployeeType      *EmployeeType  `json:"employee_type,omitempty"`
	OfficeLocation    *string        `json:"office_location,omitempty"`
	ManagerID         *uuid.UUID     `json:"manager_id,omitempty"`
	ConsultingCompany *string        `json:"consulting_company,omitempty"`
	Search            string         `json:"search,omitempty"` // Name, email, title search
	IncludeInactive   bool           `json:"include_inactive,omitempty"`
	Page              int            `json:"page" validate:"min=1"`
	PerPage           int            `json:"per_page" validate:"min=1,max=100"`
	SortBy            string         `json:"sort_by,omitempty"`
	SortOrder         string         `json:"sort_order,omitempty"`
}

// SetDefaults sets default values for the filter
func (f *EmployeeSearchFilter) SetDefaults() {
	if f.Page < 1 {
		f.Page = 1
	}
	if f.PerPage < 1 || f.PerPage > 100 {
		f.PerPage = 50
	}
	if f.SortBy == "" {
		f.SortBy = "full_name"
	}
	if f.SortOrder == "" {
		f.SortOrder = "asc"
	}
}

// Offset returns the offset for pagination
func (f *EmployeeSearchFilter) Offset() int {
	return (f.Page - 1) * f.PerPage
}
