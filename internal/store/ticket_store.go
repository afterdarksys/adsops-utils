package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/lib/pq"
	"github.com/adsops-utils/internal/models"
)

// TicketStore handles ticket database operations
type TicketStore struct {
	db *sql.DB
}

// Create creates a new ticket
func (s *TicketStore) Create(ctx context.Context, orgID, userID uuid.UUID, input *models.CreateTicketInput) (*models.Ticket, error) {
	// Generate ticket number
	var ticketNumber string
	err := s.db.QueryRowContext(ctx,
		"SELECT generate_ticket_number($1, $2)",
		orgID, time.Now().Year(),
	).Scan(&ticketNumber)
	if err != nil {
		return nil, fmt.Errorf("failed to generate ticket number: %w", err)
	}

	ticket := &models.Ticket{
		ID:                   uuid.New(),
		OrganizationID:       orgID,
		TicketNumber:         ticketNumber,
		CreatedBy:            userID,
		Title:                input.Title,
		Description:          input.Description,
		Status:               models.TicketStatusDraft,
		Priority:             input.Priority,
		RiskLevel:            input.RiskLevel,
		Industry:             input.Industry,
		ComplianceFrameworks: input.ComplianceFrameworks,
		ComplianceNotes:      input.ComplianceNotes,
		ChangeType:           input.ChangeType,
		AffectedSystems:      input.AffectedSystems,
		AffectedDataTypes:    input.AffectedDataTypes,
		ImpactDescription:    input.ImpactDescription,
		RollbackPlan:         input.RollbackPlan,
		TestingPlan:          input.TestingPlan,
		RequestedImplementationDate: input.RequestedImplementationDate,
		RequiresApprovalTypes: input.RequiresApprovalTypes,
		ApprovalDeadline:     input.ApprovalDeadline,
		CustomFields:         input.CustomFields,
		Version:              1,
		CreatedAt:            time.Now(),
		UpdatedAt:            time.Now(),
		// JIRA-like fields
		ProjectID:         input.ProjectID,
		OwningGroupID:     input.OwningGroupID,
		CustomerID:        input.CustomerID,
		ParentTicketID:    input.ParentTicketID,
		EpicID:            input.EpicID,
		StoryPoints:       input.StoryPoints,
		TimeEstimateHours: input.TimeEstimateHours,
		Labels:            input.Labels,
		Watchers:          input.Watchers,
		ExternalReference: input.ExternalReference,
		ACLInheritance:    true,
		IsConfidential:    input.IsConfidential,
	}

	query := `
		INSERT INTO change_tickets (
			id, organization_id, ticket_number, created_by, title, description,
			status, priority, risk_level, industry, compliance_frameworks,
			compliance_notes, change_type, affected_systems, affected_data_types,
			impact_description, rollback_plan, testing_plan, requested_implementation_date,
			requires_approval_types, approval_deadline, custom_fields, version,
			project_id, owning_group_id, customer_id, parent_ticket_id, epic_id,
			story_points, time_estimate_hours, labels, watchers, external_reference,
			acl_inheritance, is_confidential, created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
			$16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28,
			$29, $30, $31, $32, $33, $34, $35, $36, $37
		)
	`

	customFieldsJSON, _ := json.Marshal(ticket.CustomFields)

	_, err = s.db.ExecContext(ctx, query,
		ticket.ID, ticket.OrganizationID, ticket.TicketNumber, ticket.CreatedBy,
		ticket.Title, ticket.Description, ticket.Status, ticket.Priority,
		ticket.RiskLevel, ticket.Industry, pq.Array(ticket.ComplianceFrameworks),
		ticket.ComplianceNotes, ticket.ChangeType, pq.Array(ticket.AffectedSystems),
		pq.Array(ticket.AffectedDataTypes), ticket.ImpactDescription, ticket.RollbackPlan,
		ticket.TestingPlan, ticket.RequestedImplementationDate,
		pq.Array(ticket.RequiresApprovalTypes), ticket.ApprovalDeadline, customFieldsJSON,
		ticket.Version, ticket.ProjectID, ticket.OwningGroupID, ticket.CustomerID,
		ticket.ParentTicketID, ticket.EpicID, ticket.StoryPoints, ticket.TimeEstimateHours,
		pq.Array(ticket.Labels), pq.Array(ticket.Watchers), ticket.ExternalReference,
		ticket.ACLInheritance, ticket.IsConfidential, ticket.CreatedAt, ticket.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create ticket: %w", err)
	}

	return ticket, nil
}

// GetByID retrieves a ticket by ID
func (s *TicketStore) GetByID(ctx context.Context, orgID, ticketID uuid.UUID) (*models.Ticket, error) {
	query := `
		SELECT
			id, organization_id, ticket_number, created_by, assigned_to, title,
			description, status, priority, risk_level, industry, compliance_frameworks,
			compliance_notes, change_type, affected_systems, affected_data_types,
			impact_description, rollback_plan, testing_plan, requested_implementation_date,
			scheduled_start, scheduled_end, actual_start, actual_end,
			requires_approval_types, approval_deadline, attachment_urls, custom_fields,
			submitted_at, submitted_snapshot, version, created_at, updated_at,
			closed_at, deleted_at, deletion_reason,
			project_id, owning_group_id, customer_id, parent_ticket_id, epic_id,
			story_points, time_estimate_hours, time_spent_hours, labels, watchers,
			external_reference, acl_inheritance, is_confidential
		FROM change_tickets
		WHERE id = $1 AND organization_id = $2 AND deleted_at IS NULL
	`

	ticket := &models.Ticket{}
	var complianceFrameworks, approvalTypes, affectedSystems, affectedDataTypes, attachmentURLs, labels []string
	var watchers []string

	err := s.db.QueryRowContext(ctx, query, ticketID, orgID).Scan(
		&ticket.ID, &ticket.OrganizationID, &ticket.TicketNumber, &ticket.CreatedBy,
		&ticket.AssignedTo, &ticket.Title, &ticket.Description, &ticket.Status,
		&ticket.Priority, &ticket.RiskLevel, &ticket.Industry, pq.Array(&complianceFrameworks),
		&ticket.ComplianceNotes, &ticket.ChangeType, pq.Array(&affectedSystems),
		pq.Array(&affectedDataTypes), &ticket.ImpactDescription, &ticket.RollbackPlan,
		&ticket.TestingPlan, &ticket.RequestedImplementationDate, &ticket.ScheduledStart,
		&ticket.ScheduledEnd, &ticket.ActualStart, &ticket.ActualEnd,
		pq.Array(&approvalTypes), &ticket.ApprovalDeadline, pq.Array(&attachmentURLs),
		&ticket.CustomFields, &ticket.SubmittedAt, &ticket.SubmittedSnapshot,
		&ticket.Version, &ticket.CreatedAt, &ticket.UpdatedAt, &ticket.ClosedAt,
		&ticket.DeletedAt, &ticket.DeletionReason,
		&ticket.ProjectID, &ticket.OwningGroupID, &ticket.CustomerID,
		&ticket.ParentTicketID, &ticket.EpicID, &ticket.StoryPoints,
		&ticket.TimeEstimateHours, &ticket.TimeSpentHours, pq.Array(&labels),
		pq.Array(&watchers), &ticket.ExternalReference, &ticket.ACLInheritance,
		&ticket.IsConfidential,
	)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("ticket not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get ticket: %w", err)
	}

	// Convert string arrays to typed arrays
	ticket.ComplianceFrameworks = make([]models.ComplianceFramework, len(complianceFrameworks))
	for i, cf := range complianceFrameworks {
		ticket.ComplianceFrameworks[i] = models.ComplianceFramework(cf)
	}
	ticket.RequiresApprovalTypes = make([]models.ApprovalType, len(approvalTypes))
	for i, at := range approvalTypes {
		ticket.RequiresApprovalTypes[i] = models.ApprovalType(at)
	}
	ticket.AffectedSystems = affectedSystems
	ticket.AffectedDataTypes = affectedDataTypes
	ticket.AttachmentURLs = attachmentURLs
	ticket.Labels = labels

	// Convert watcher strings to UUIDs
	ticket.Watchers = make([]uuid.UUID, 0, len(watchers))
	for _, w := range watchers {
		if uid, err := uuid.Parse(w); err == nil {
			ticket.Watchers = append(ticket.Watchers, uid)
		}
	}

	return ticket, nil
}

// GetByNumber retrieves a ticket by ticket number
func (s *TicketStore) GetByNumber(ctx context.Context, orgID uuid.UUID, ticketNumber string) (*models.Ticket, error) {
	var ticketID uuid.UUID
	err := s.db.QueryRowContext(ctx,
		"SELECT id FROM change_tickets WHERE organization_id = $1 AND ticket_number = $2 AND deleted_at IS NULL",
		orgID, ticketNumber,
	).Scan(&ticketID)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("ticket not found")
	}
	if err != nil {
		return nil, err
	}
	return s.GetByID(ctx, orgID, ticketID)
}

// List retrieves tickets with filtering
func (s *TicketStore) List(ctx context.Context, orgID uuid.UUID, filter *models.TicketListFilter) ([]models.Ticket, int, error) {
	filter.SetDefaults()

	var conditions []string
	var args []interface{}
	argNum := 1

	conditions = append(conditions, fmt.Sprintf("organization_id = $%d", argNum))
	args = append(args, orgID)
	argNum++

	conditions = append(conditions, "deleted_at IS NULL")

	if len(filter.Status) > 0 {
		conditions = append(conditions, fmt.Sprintf("status = ANY($%d)", argNum))
		args = append(args, pq.Array(filter.Status))
		argNum++
	}

	if len(filter.Priority) > 0 {
		conditions = append(conditions, fmt.Sprintf("priority = ANY($%d)", argNum))
		args = append(args, pq.Array(filter.Priority))
		argNum++
	}

	if filter.CreatedBy != nil {
		conditions = append(conditions, fmt.Sprintf("created_by = $%d", argNum))
		args = append(args, *filter.CreatedBy)
		argNum++
	}

	if filter.AssignedTo != nil {
		conditions = append(conditions, fmt.Sprintf("assigned_to = $%d", argNum))
		args = append(args, *filter.AssignedTo)
		argNum++
	}

	if filter.ProjectID != nil {
		conditions = append(conditions, fmt.Sprintf("project_id = $%d", argNum))
		args = append(args, *filter.ProjectID)
		argNum++
	}

	if filter.OwningGroupID != nil {
		conditions = append(conditions, fmt.Sprintf("owning_group_id = $%d", argNum))
		args = append(args, *filter.OwningGroupID)
		argNum++
	}

	if filter.CustomerID != nil {
		conditions = append(conditions, fmt.Sprintf("customer_id = $%d", argNum))
		args = append(args, *filter.CustomerID)
		argNum++
	}

	if filter.EpicID != nil {
		conditions = append(conditions, fmt.Sprintf("epic_id = $%d", argNum))
		args = append(args, *filter.EpicID)
		argNum++
	}

	if filter.NeedsAssignment {
		conditions = append(conditions, "assigned_to IS NULL")
		conditions = append(conditions, "status IN ('submitted', 'in_review', 'update_requested')")
	}

	if filter.Search != "" {
		conditions = append(conditions, fmt.Sprintf("(title ILIKE $%d OR description ILIKE $%d OR ticket_number ILIKE $%d)", argNum, argNum+1, argNum+2))
		searchTerm := "%" + filter.Search + "%"
		args = append(args, searchTerm, searchTerm, searchTerm)
		argNum += 3
	}

	whereClause := strings.Join(conditions, " AND ")

	// Count total
	var total int
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM change_tickets WHERE %s", whereClause)
	err := s.db.QueryRowContext(ctx, countQuery, args...).Scan(&total)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count tickets: %w", err)
	}

	// Get tickets
	validSortFields := map[string]bool{
		"created_at": true, "updated_at": true, "priority": true,
		"status": true, "ticket_number": true, "title": true,
	}
	sortBy := "created_at"
	if validSortFields[filter.SortBy] {
		sortBy = filter.SortBy
	}

	sortOrder := "DESC"
	if filter.SortOrder == "asc" {
		sortOrder = "ASC"
	}

	query := fmt.Sprintf(`
		SELECT id, ticket_number, title, status, priority, risk_level,
		       created_by, assigned_to, created_at, updated_at,
		       project_id, owning_group_id, customer_id
		FROM change_tickets
		WHERE %s
		ORDER BY %s %s
		LIMIT $%d OFFSET $%d
	`, whereClause, sortBy, sortOrder, argNum, argNum+1)

	args = append(args, filter.PerPage, filter.Offset())

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list tickets: %w", err)
	}
	defer rows.Close()

	var tickets []models.Ticket
	for rows.Next() {
		var t models.Ticket
		err := rows.Scan(
			&t.ID, &t.TicketNumber, &t.Title, &t.Status, &t.Priority,
			&t.RiskLevel, &t.CreatedBy, &t.AssignedTo, &t.CreatedAt, &t.UpdatedAt,
			&t.ProjectID, &t.OwningGroupID, &t.CustomerID,
		)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to scan ticket: %w", err)
		}
		tickets = append(tickets, t)
	}

	return tickets, total, nil
}

// Update updates a ticket
func (s *TicketStore) Update(ctx context.Context, orgID, ticketID uuid.UUID, input *models.UpdateTicketInput) (*models.Ticket, error) {
	// Get current ticket
	ticket, err := s.GetByID(ctx, orgID, ticketID)
	if err != nil {
		return nil, err
	}

	if !ticket.CanEdit() {
		return nil, fmt.Errorf("ticket cannot be edited in current status")
	}

	// Build update query dynamically
	var updates []string
	var args []interface{}
	argNum := 1

	if input.Title != nil {
		updates = append(updates, fmt.Sprintf("title = $%d", argNum))
		args = append(args, *input.Title)
		argNum++
	}

	if input.Description != nil {
		updates = append(updates, fmt.Sprintf("description = $%d", argNum))
		args = append(args, *input.Description)
		argNum++
	}

	if input.Priority != nil {
		updates = append(updates, fmt.Sprintf("priority = $%d", argNum))
		args = append(args, *input.Priority)
		argNum++
	}

	if input.RiskLevel != nil {
		updates = append(updates, fmt.Sprintf("risk_level = $%d", argNum))
		args = append(args, *input.RiskLevel)
		argNum++
	}

	if input.AssignedTo != nil {
		updates = append(updates, fmt.Sprintf("assigned_to = $%d", argNum))
		args = append(args, *input.AssignedTo)
		argNum++
	}

	if input.ProjectID != nil {
		updates = append(updates, fmt.Sprintf("project_id = $%d", argNum))
		args = append(args, *input.ProjectID)
		argNum++
	}

	if input.OwningGroupID != nil {
		updates = append(updates, fmt.Sprintf("owning_group_id = $%d", argNum))
		args = append(args, *input.OwningGroupID)
		argNum++
	}

	if input.StoryPoints != nil {
		updates = append(updates, fmt.Sprintf("story_points = $%d", argNum))
		args = append(args, *input.StoryPoints)
		argNum++
	}

	if input.Labels != nil {
		updates = append(updates, fmt.Sprintf("labels = $%d", argNum))
		args = append(args, pq.Array(input.Labels))
		argNum++
	}

	if len(updates) == 0 {
		return ticket, nil
	}

	// Increment version
	updates = append(updates, fmt.Sprintf("version = version + 1"))
	updates = append(updates, "updated_at = NOW()")

	query := fmt.Sprintf(
		"UPDATE change_tickets SET %s WHERE id = $%d AND organization_id = $%d",
		strings.Join(updates, ", "), argNum, argNum+1,
	)
	args = append(args, ticketID, orgID)

	_, err = s.db.ExecContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to update ticket: %w", err)
	}

	return s.GetByID(ctx, orgID, ticketID)
}

// UpdateStatus updates the status of a ticket
func (s *TicketStore) UpdateStatus(ctx context.Context, orgID, ticketID uuid.UUID, status models.TicketStatus) error {
	query := `
		UPDATE change_tickets
		SET status = $1, updated_at = NOW()
		WHERE id = $2 AND organization_id = $3
	`
	_, err := s.db.ExecContext(ctx, query, status, ticketID, orgID)
	return err
}

// Submit submits a ticket for approval
func (s *TicketStore) Submit(ctx context.Context, orgID, ticketID uuid.UUID) error {
	ticket, err := s.GetByID(ctx, orgID, ticketID)
	if err != nil {
		return err
	}

	if !ticket.CanSubmit() {
		return fmt.Errorf("ticket cannot be submitted in current status")
	}

	// Create snapshot
	snapshot, _ := json.Marshal(ticket)

	query := `
		UPDATE change_tickets
		SET status = 'submitted',
		    submitted_at = NOW(),
		    submitted_snapshot = $1,
		    updated_at = NOW()
		WHERE id = $2 AND organization_id = $3
	`
	_, err = s.db.ExecContext(ctx, query, snapshot, ticketID, orgID)
	return err
}

// Close closes a ticket
func (s *TicketStore) Close(ctx context.Context, orgID, ticketID uuid.UUID) error {
	ticket, err := s.GetByID(ctx, orgID, ticketID)
	if err != nil {
		return err
	}

	if !ticket.CanClose() {
		return fmt.Errorf("ticket cannot be closed in current status")
	}

	query := `
		UPDATE change_tickets
		SET status = 'closed',
		    closed_at = NOW(),
		    updated_at = NOW()
		WHERE id = $2 AND organization_id = $3
	`
	_, err = s.db.ExecContext(ctx, query, ticketID, orgID)
	return err
}

// Cancel cancels a ticket
func (s *TicketStore) Cancel(ctx context.Context, orgID, ticketID uuid.UUID, reason string) error {
	ticket, err := s.GetByID(ctx, orgID, ticketID)
	if err != nil {
		return err
	}

	if !ticket.CanCancel() {
		return fmt.Errorf("ticket cannot be cancelled in current status")
	}

	query := `
		UPDATE change_tickets
		SET status = 'cancelled',
		    deletion_reason = $1,
		    updated_at = NOW()
		WHERE id = $2 AND organization_id = $3
	`
	_, err = s.db.ExecContext(ctx, query, reason, ticketID, orgID)
	return err
}

// GetQueue retrieves tickets that need assignment (for ticket queue bot)
func (s *TicketStore) GetQueue(ctx context.Context, orgID uuid.UUID) ([]models.Ticket, error) {
	filter := &models.TicketListFilter{
		NeedsAssignment: true,
		SortBy:          "created_at",
		SortOrder:       "asc",
		PerPage:         100,
	}
	tickets, _, err := s.List(ctx, orgID, filter)
	return tickets, err
}

// Assign assigns a ticket to a user
func (s *TicketStore) Assign(ctx context.Context, orgID, ticketID, userID uuid.UUID) error {
	query := `
		UPDATE change_tickets
		SET assigned_to = $1, updated_at = NOW()
		WHERE id = $2 AND organization_id = $3
	`
	_, err := s.db.ExecContext(ctx, query, userID, ticketID, orgID)
	return err
}

// AddWatcher adds a watcher to a ticket
func (s *TicketStore) AddWatcher(ctx context.Context, orgID, ticketID, userID uuid.UUID) error {
	query := `
		UPDATE change_tickets
		SET watchers = array_append(watchers, $1), updated_at = NOW()
		WHERE id = $2 AND organization_id = $3 AND NOT ($1 = ANY(watchers))
	`
	_, err := s.db.ExecContext(ctx, query, userID, ticketID, orgID)
	return err
}

// RemoveWatcher removes a watcher from a ticket
func (s *TicketStore) RemoveWatcher(ctx context.Context, orgID, ticketID, userID uuid.UUID) error {
	query := `
		UPDATE change_tickets
		SET watchers = array_remove(watchers, $1), updated_at = NOW()
		WHERE id = $2 AND organization_id = $3
	`
	_, err := s.db.ExecContext(ctx, query, userID, ticketID, orgID)
	return err
}

// LinkRepository links a repository to a ticket
func (s *TicketStore) LinkRepository(ctx context.Context, ticketID, repoID, linkedBy uuid.UUID, input *models.LinkRepositoryInput) error {
	query := `
		INSERT INTO ticket_repositories (ticket_id, repository_id, linked_by, link_type, branch_name, commit_sha, pr_number, notes)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (ticket_id, repository_id) DO UPDATE
		SET link_type = $4, branch_name = $5, commit_sha = $6, pr_number = $7, notes = $8
	`
	linkType := "related"
	if input.LinkType != "" {
		linkType = input.LinkType
	}
	_, err := s.db.ExecContext(ctx, query, ticketID, input.RepositoryID, linkedBy, linkType, input.BranchName, input.CommitSHA, input.PRNumber, input.Notes)
	return err
}

// UnlinkRepository unlinks a repository from a ticket
func (s *TicketStore) UnlinkRepository(ctx context.Context, ticketID, repoID uuid.UUID) error {
	query := "DELETE FROM ticket_repositories WHERE ticket_id = $1 AND repository_id = $2"
	_, err := s.db.ExecContext(ctx, query, ticketID, repoID)
	return err
}
