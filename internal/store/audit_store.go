package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/google/uuid"
	"github.com/lib/pq"
	"github.com/adsops-utils/internal/models"
)

// AuditStore handles audit log database operations
type AuditStore struct {
	db *sql.DB
}

// LogTicketAccess logs an access event for a ticket (SOX compliance)
func (s *AuditStore) LogTicketAccess(ctx context.Context, ticketID, userID uuid.UUID, action string, ipAddress, userAgent *string, changes map[string]interface{}) error {
	// Get ticket org and compliance info
	var orgID uuid.UUID
	var complianceFrameworks []string
	err := s.db.QueryRowContext(ctx,
		"SELECT organization_id, compliance_frameworks FROM change_tickets WHERE id = $1",
		ticketID,
	).Scan(&orgID, pq.Array(&complianceFrameworks))
	if err != nil {
		return fmt.Errorf("failed to get ticket info: %w", err)
	}

	actionCategory := getActionCategory(action)
	isComplianceRelevant := isComplianceRelevantAction(action)

	changesJSON, _ := json.Marshal(changes)

	query := `
		INSERT INTO ticket_audit_log (
			ticket_id, organization_id, user_id, action, action_category,
			changes, ip_address, user_agent, is_compliance_relevant,
			compliance_frameworks, requires_review
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
	`

	_, err = s.db.ExecContext(ctx, query,
		ticketID, orgID, userID, action, actionCategory,
		changesJSON, ipAddress, userAgent, isComplianceRelevant,
		pq.Array(complianceFrameworks), isComplianceRelevant,
	)
	return err
}

// LogTicketView logs a view event for a ticket
func (s *AuditStore) LogTicketView(ctx context.Context, ticketID, userID uuid.UUID, ipAddress, userAgent *string) error {
	return s.LogTicketAccess(ctx, ticketID, userID, "view", ipAddress, userAgent, nil)
}

// LogTicketEdit logs an edit event for a ticket
func (s *AuditStore) LogTicketEdit(ctx context.Context, ticketID, userID uuid.UUID, ipAddress, userAgent *string, changes map[string]interface{}) error {
	return s.LogTicketAccess(ctx, ticketID, userID, "edit", ipAddress, userAgent, changes)
}

// LogTicketStatusChange logs a status change event
func (s *AuditStore) LogTicketStatusChange(ctx context.Context, ticketID, userID uuid.UUID, oldStatus, newStatus string, ipAddress, userAgent *string) error {
	changes := map[string]interface{}{
		"old_status": oldStatus,
		"new_status": newStatus,
	}
	return s.LogTicketAccess(ctx, ticketID, userID, "status_change", ipAddress, userAgent, changes)
}

// GetTicketAuditLog retrieves audit log entries for a ticket
func (s *AuditStore) GetTicketAuditLog(ctx context.Context, ticketID uuid.UUID, filter *models.AuditLogFilter) ([]models.TicketAuditLog, int, error) {
	filter.SetDefaults()

	var conditions []string
	var args []interface{}
	argNum := 1

	conditions = append(conditions, fmt.Sprintf("ticket_id = $%d", argNum))
	args = append(args, ticketID)
	argNum++

	if filter.UserID != nil {
		conditions = append(conditions, fmt.Sprintf("user_id = $%d", argNum))
		args = append(args, *filter.UserID)
		argNum++
	}

	if filter.Action != nil {
		conditions = append(conditions, fmt.Sprintf("action = $%d", argNum))
		args = append(args, *filter.Action)
		argNum++
	}

	if filter.ActionCategory != nil {
		conditions = append(conditions, fmt.Sprintf("action_category = $%d", argNum))
		args = append(args, *filter.ActionCategory)
		argNum++
	}

	if filter.IsComplianceRelevant != nil {
		conditions = append(conditions, fmt.Sprintf("is_compliance_relevant = $%d", argNum))
		args = append(args, *filter.IsComplianceRelevant)
		argNum++
	}

	if filter.RequiresReview != nil {
		conditions = append(conditions, fmt.Sprintf("requires_review = $%d", argNum))
		args = append(args, *filter.RequiresReview)
		argNum++
	}

	whereClause := strings.Join(conditions, " AND ")

	// Count total
	var total int
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM ticket_audit_log WHERE %s", whereClause)
	err := s.db.QueryRowContext(ctx, countQuery, args...).Scan(&total)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count audit logs: %w", err)
	}

	// Get logs
	query := fmt.Sprintf(`
		SELECT id, ticket_id, organization_id, user_id, action, action_category,
		       field_name, old_value, new_value, changes, ip_address, user_agent,
		       session_id, request_id, is_compliance_relevant, compliance_frameworks,
		       requires_review, reviewed_by, reviewed_at, created_at
		FROM ticket_audit_log
		WHERE %s
		ORDER BY created_at DESC
		LIMIT $%d OFFSET $%d
	`, whereClause, argNum, argNum+1)

	args = append(args, filter.PerPage, filter.Offset())

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get audit logs: %w", err)
	}
	defer rows.Close()

	var logs []models.TicketAuditLog
	for rows.Next() {
		var log models.TicketAuditLog
		var changesJSON []byte
		var complianceFrameworks []string
		err := rows.Scan(
			&log.ID, &log.TicketID, &log.OrganizationID, &log.UserID,
			&log.Action, &log.ActionCategory, &log.FieldName, &log.OldValue,
			&log.NewValue, &changesJSON, &log.IPAddress, &log.UserAgent,
			&log.SessionID, &log.RequestID, &log.IsComplianceRelevant,
			pq.Array(&complianceFrameworks), &log.RequiresReview,
			&log.ReviewedBy, &log.ReviewedAt, &log.CreatedAt,
		)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to scan audit log: %w", err)
		}

		if changesJSON != nil {
			json.Unmarshal(changesJSON, &log.Changes)
		}

		log.ComplianceFrameworks = make([]models.ComplianceFramework, len(complianceFrameworks))
		for i, cf := range complianceFrameworks {
			log.ComplianceFrameworks[i] = models.ComplianceFramework(cf)
		}

		logs = append(logs, log)
	}

	return logs, total, nil
}

// MarkReviewed marks an audit log entry as reviewed
func (s *AuditStore) MarkReviewed(ctx context.Context, auditID, reviewerID uuid.UUID) error {
	query := `
		UPDATE ticket_audit_log
		SET reviewed_by = $1, reviewed_at = NOW()
		WHERE id = $2 AND requires_review = true AND reviewed_at IS NULL
	`
	_, err := s.db.ExecContext(ctx, query, reviewerID, auditID)
	return err
}

// GetPendingReviews retrieves audit log entries pending review
func (s *AuditStore) GetPendingReviews(ctx context.Context, orgID uuid.UUID) ([]models.TicketAuditLog, error) {
	query := `
		SELECT id, ticket_id, organization_id, user_id, action, action_category,
		       changes, ip_address, is_compliance_relevant, compliance_frameworks,
		       requires_review, created_at
		FROM ticket_audit_log
		WHERE organization_id = $1 AND requires_review = true AND reviewed_at IS NULL
		ORDER BY created_at ASC
		LIMIT 100
	`

	rows, err := s.db.QueryContext(ctx, query, orgID)
	if err != nil {
		return nil, fmt.Errorf("failed to get pending reviews: %w", err)
	}
	defer rows.Close()

	var logs []models.TicketAuditLog
	for rows.Next() {
		var log models.TicketAuditLog
		var changesJSON []byte
		var complianceFrameworks []string
		err := rows.Scan(
			&log.ID, &log.TicketID, &log.OrganizationID, &log.UserID,
			&log.Action, &log.ActionCategory, &changesJSON, &log.IPAddress,
			&log.IsComplianceRelevant, pq.Array(&complianceFrameworks),
			&log.RequiresReview, &log.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan audit log: %w", err)
		}

		if changesJSON != nil {
			json.Unmarshal(changesJSON, &log.Changes)
		}

		log.ComplianceFrameworks = make([]models.ComplianceFramework, len(complianceFrameworks))
		for i, cf := range complianceFrameworks {
			log.ComplianceFrameworks[i] = models.ComplianceFramework(cf)
		}

		logs = append(logs, log)
	}

	return logs, nil
}

func getActionCategory(action string) string {
	switch action {
	case "view", "search", "export":
		return "access"
	case "create", "update", "edit", "delete":
		return "modification"
	case "approve", "deny", "submit", "status_change":
		return "approval"
	default:
		return "other"
	}
}

func isComplianceRelevantAction(action string) bool {
	switch action {
	case "create", "update", "edit", "delete", "approve", "deny", "submit", "status_change":
		return true
	default:
		return false
	}
}
