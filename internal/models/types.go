package models

import "github.com/google/uuid"

// IndustryType represents supported industries
type IndustryType string

const (
	IndustryHealthcare  IndustryType = "healthcare"
	IndustryIT          IndustryType = "it"
	IndustryGovernment  IndustryType = "government"
	IndustryInsurance   IndustryType = "insurance"
	IndustryFinance     IndustryType = "finance"
)

// Valid returns true if the industry type is valid
func (i IndustryType) Valid() bool {
	switch i {
	case IndustryHealthcare, IndustryIT, IndustryGovernment, IndustryInsurance, IndustryFinance:
		return true
	}
	return false
}

// ComplianceFramework represents regulatory compliance frameworks
type ComplianceFramework string

const (
	ComplianceGLBA              ComplianceFramework = "glba"
	ComplianceSOX               ComplianceFramework = "sox"
	ComplianceHIPAA             ComplianceFramework = "hipaa"
	ComplianceBankingSecrecyAct ComplianceFramework = "banking_secrecy_act"
	ComplianceGDPR              ComplianceFramework = "gdpr"
	ComplianceCustom            ComplianceFramework = "custom"
)

// Valid returns true if the compliance framework is valid
func (c ComplianceFramework) Valid() bool {
	switch c {
	case ComplianceGLBA, ComplianceSOX, ComplianceHIPAA, ComplianceBankingSecrecyAct, ComplianceGDPR, ComplianceCustom:
		return true
	}
	return false
}

// TicketStatus represents the status of a change ticket
type TicketStatus string

const (
	TicketStatusDraft             TicketStatus = "draft"
	TicketStatusSubmitted         TicketStatus = "submitted"
	TicketStatusInReview          TicketStatus = "in_review"
	TicketStatusApproved          TicketStatus = "approved"
	TicketStatusPartiallyApproved TicketStatus = "partially_approved"
	TicketStatusDenied            TicketStatus = "denied"
	TicketStatusUpdateRequested   TicketStatus = "update_requested"
	TicketStatusImplementing      TicketStatus = "implementing"
	TicketStatusCompleted         TicketStatus = "completed"
	TicketStatusClosed            TicketStatus = "closed"
	TicketStatusCancelled         TicketStatus = "cancelled"
)

// Valid returns true if the ticket status is valid
func (t TicketStatus) Valid() bool {
	switch t {
	case TicketStatusDraft, TicketStatusSubmitted, TicketStatusInReview, TicketStatusApproved,
		TicketStatusPartiallyApproved, TicketStatusDenied, TicketStatusUpdateRequested,
		TicketStatusImplementing, TicketStatusCompleted, TicketStatusClosed, TicketStatusCancelled:
		return true
	}
	return false
}

// IsOpen returns true if the ticket is in an open state
func (t TicketStatus) IsOpen() bool {
	switch t {
	case TicketStatusDraft, TicketStatusSubmitted, TicketStatusInReview,
		TicketStatusPartiallyApproved, TicketStatusUpdateRequested, TicketStatusImplementing:
		return true
	}
	return false
}

// ApprovalType represents different types of approvals
type ApprovalType string

const (
	ApprovalTypeOperations            ApprovalType = "operations"
	ApprovalTypeIT                    ApprovalType = "it"
	ApprovalTypeRisk                  ApprovalType = "risk"
	ApprovalTypeChangeManagementBoard ApprovalType = "change_management_board"
	ApprovalTypeAIOps                 ApprovalType = "ai_ops"
	ApprovalTypeSecurity              ApprovalType = "security"
	ApprovalTypeNetworkEngineering    ApprovalType = "network_engineering"
	ApprovalTypeCloud                 ApprovalType = "cloud"
)

// Valid returns true if the approval type is valid
func (a ApprovalType) Valid() bool {
	switch a {
	case ApprovalTypeOperations, ApprovalTypeIT, ApprovalTypeRisk, ApprovalTypeChangeManagementBoard,
		ApprovalTypeAIOps, ApprovalTypeSecurity, ApprovalTypeNetworkEngineering, ApprovalTypeCloud:
		return true
	}
	return false
}

// DisplayName returns a human-readable name for the approval type
func (a ApprovalType) DisplayName() string {
	switch a {
	case ApprovalTypeOperations:
		return "Operations Approval"
	case ApprovalTypeIT:
		return "IT Approval"
	case ApprovalTypeRisk:
		return "Risk Approval"
	case ApprovalTypeChangeManagementBoard:
		return "Change Management Board Approval"
	case ApprovalTypeAIOps:
		return "AI Ops Approval"
	case ApprovalTypeSecurity:
		return "Security Approval"
	case ApprovalTypeNetworkEngineering:
		return "Network Engineering Approval"
	case ApprovalTypeCloud:
		return "Cloud Approval"
	}
	return string(a)
}

// ApprovalStatus represents the status of an approval
type ApprovalStatus string

const (
	ApprovalStatusPending         ApprovalStatus = "pending"
	ApprovalStatusApproved        ApprovalStatus = "approved"
	ApprovalStatusDenied          ApprovalStatus = "denied"
	ApprovalStatusUpdateRequested ApprovalStatus = "update_requested"
	ApprovalStatusExpired         ApprovalStatus = "expired"
)

// Valid returns true if the approval status is valid
func (a ApprovalStatus) Valid() bool {
	switch a {
	case ApprovalStatusPending, ApprovalStatusApproved, ApprovalStatusDenied, ApprovalStatusUpdateRequested, ApprovalStatusExpired:
		return true
	}
	return false
}

// TicketPriority represents ticket priority levels
type TicketPriority string

const (
	TicketPriorityEmergency TicketPriority = "emergency" // < 1 hour
	TicketPriorityUrgent    TicketPriority = "urgent"    // < 4 hours
	TicketPriorityHigh      TicketPriority = "high"      // < 24 hours
	TicketPriorityNormal    TicketPriority = "normal"    // < 72 hours
	TicketPriorityLow       TicketPriority = "low"       // < 7 days
)

// Valid returns true if the priority is valid
func (p TicketPriority) Valid() bool {
	switch p {
	case TicketPriorityEmergency, TicketPriorityUrgent, TicketPriorityHigh, TicketPriorityNormal, TicketPriorityLow:
		return true
	}
	return false
}

// RiskLevel represents risk assessment levels
type RiskLevel string

const (
	RiskLevelCritical RiskLevel = "critical"
	RiskLevelHigh     RiskLevel = "high"
	RiskLevelMedium   RiskLevel = "medium"
	RiskLevelLow      RiskLevel = "low"
)

// Valid returns true if the risk level is valid
func (r RiskLevel) Valid() bool {
	switch r {
	case RiskLevelCritical, RiskLevelHigh, RiskLevelMedium, RiskLevelLow:
		return true
	}
	return false
}

// UserRole represents user roles in the system
type UserRole string

const (
	UserRoleAdmin    UserRole = "admin"
	UserRoleApprover UserRole = "approver"
	UserRoleUser     UserRole = "user"
	UserRoleAuditor  UserRole = "auditor"
)

// Valid returns true if the user role is valid
func (u UserRole) Valid() bool {
	switch u {
	case UserRoleAdmin, UserRoleApprover, UserRoleUser, UserRoleAuditor:
		return true
	}
	return false
}

// PrincipalType identifies whether an actor is a human user, AI agent, or service
type PrincipalType string

const (
	PrincipalTypeUser    PrincipalType = "user"
	PrincipalTypeAgent   PrincipalType = "agent"
	PrincipalTypeService PrincipalType = "service"
)

// Valid returns true if the principal type is valid
func (p PrincipalType) Valid() bool {
	switch p {
	case PrincipalTypeUser, PrincipalTypeAgent, PrincipalTypeService:
		return true
	}
	return false
}

// Principal represents a resolved actor — user, agent, or service
type Principal struct {
	ID   uuid.UUID     `json:"id"`
	Type PrincipalType `json:"type"`
	Name string        `json:"name"`
}
