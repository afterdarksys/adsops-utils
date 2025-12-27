package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/google/uuid"
	"github.com/adsops-utils/internal/models"
)

// RepositoryStore handles repository database operations
type RepositoryStore struct {
	db *sql.DB
}

// Create creates a new repository
func (s *RepositoryStore) Create(ctx context.Context, orgID uuid.UUID, input *models.CreateRepositoryInput) (*models.Repository, error) {
	repo := &models.Repository{
		ID:             uuid.New(),
		OrganizationID: orgID,
		Name:           input.Name,
		URL:            input.URL,
		Provider:       input.Provider,
		OwnerUserID:    input.OwnerUserID,
		OwnerGroupID:   input.OwnerGroupID,
		DefaultBranch:  "main",
		IsActive:       true,
		IsPrivate:      true,
		Description:    input.Description,
		Language:       input.Language,
	}

	if input.DefaultBranch != "" {
		repo.DefaultBranch = input.DefaultBranch
	}
	if input.IsPrivate != nil {
		repo.IsPrivate = *input.IsPrivate
	}

	query := `
		INSERT INTO repositories (
			id, organization_id, name, url, provider, owner_user_id, owner_group_id,
			default_branch, is_active, is_private, description, language
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`

	_, err := s.db.ExecContext(ctx, query,
		repo.ID, repo.OrganizationID, repo.Name, repo.URL, repo.Provider,
		repo.OwnerUserID, repo.OwnerGroupID, repo.DefaultBranch,
		repo.IsActive, repo.IsPrivate, repo.Description, repo.Language,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create repository: %w", err)
	}

	return repo, nil
}

// GetByID retrieves a repository by ID
func (s *RepositoryStore) GetByID(ctx context.Context, orgID, repoID uuid.UUID) (*models.Repository, error) {
	query := `
		SELECT id, organization_id, name, url, provider, owner_user_id, owner_group_id,
		       default_branch, is_active, is_private, description, language,
		       last_synced_at, created_at, updated_at
		FROM repositories
		WHERE id = $1 AND organization_id = $2
	`

	repo := &models.Repository{}
	err := s.db.QueryRowContext(ctx, query, repoID, orgID).Scan(
		&repo.ID, &repo.OrganizationID, &repo.Name, &repo.URL, &repo.Provider,
		&repo.OwnerUserID, &repo.OwnerGroupID, &repo.DefaultBranch,
		&repo.IsActive, &repo.IsPrivate, &repo.Description, &repo.Language,
		&repo.LastSyncedAt, &repo.CreatedAt, &repo.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("repository not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get repository: %w", err)
	}

	return repo, nil
}

// GetByURL retrieves a repository by URL
func (s *RepositoryStore) GetByURL(ctx context.Context, orgID uuid.UUID, url string) (*models.Repository, error) {
	var repoID uuid.UUID
	err := s.db.QueryRowContext(ctx,
		"SELECT id FROM repositories WHERE organization_id = $1 AND url = $2",
		orgID, url,
	).Scan(&repoID)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("repository not found")
	}
	if err != nil {
		return nil, err
	}
	return s.GetByID(ctx, orgID, repoID)
}

// List retrieves repositories with filtering
func (s *RepositoryStore) List(ctx context.Context, orgID uuid.UUID, filter *models.RepositoryListFilter) ([]models.Repository, int, error) {
	filter.SetDefaults()

	var conditions []string
	var args []interface{}
	argNum := 1

	conditions = append(conditions, fmt.Sprintf("organization_id = $%d", argNum))
	args = append(args, orgID)
	argNum++

	if filter.Provider != nil {
		conditions = append(conditions, fmt.Sprintf("provider = $%d", argNum))
		args = append(args, *filter.Provider)
		argNum++
	}

	if filter.OwnerUserID != nil {
		conditions = append(conditions, fmt.Sprintf("owner_user_id = $%d", argNum))
		args = append(args, *filter.OwnerUserID)
		argNum++
	}

	if filter.OwnerGroupID != nil {
		conditions = append(conditions, fmt.Sprintf("owner_group_id = $%d", argNum))
		args = append(args, *filter.OwnerGroupID)
		argNum++
	}

	if filter.IsActive != nil {
		conditions = append(conditions, fmt.Sprintf("is_active = $%d", argNum))
		args = append(args, *filter.IsActive)
		argNum++
	}

	if filter.Search != "" {
		conditions = append(conditions, fmt.Sprintf("(name ILIKE $%d OR url ILIKE $%d)", argNum, argNum+1))
		searchTerm := "%" + filter.Search + "%"
		args = append(args, searchTerm, searchTerm)
		argNum += 2
	}

	whereClause := strings.Join(conditions, " AND ")

	// Count total
	var total int
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM repositories WHERE %s", whereClause)
	err := s.db.QueryRowContext(ctx, countQuery, args...).Scan(&total)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count repositories: %w", err)
	}

	// Get repositories
	query := fmt.Sprintf(`
		SELECT id, organization_id, name, url, provider, owner_user_id, owner_group_id,
		       default_branch, is_active, is_private, description, language,
		       last_synced_at, created_at, updated_at
		FROM repositories
		WHERE %s
		ORDER BY %s %s
		LIMIT $%d OFFSET $%d
	`, whereClause, filter.SortBy, filter.SortOrder, argNum, argNum+1)

	args = append(args, filter.PerPage, filter.Offset())

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list repositories: %w", err)
	}
	defer rows.Close()

	var repos []models.Repository
	for rows.Next() {
		var r models.Repository
		err := rows.Scan(
			&r.ID, &r.OrganizationID, &r.Name, &r.URL, &r.Provider,
			&r.OwnerUserID, &r.OwnerGroupID, &r.DefaultBranch,
			&r.IsActive, &r.IsPrivate, &r.Description, &r.Language,
			&r.LastSyncedAt, &r.CreatedAt, &r.UpdatedAt,
		)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to scan repository: %w", err)
		}
		repos = append(repos, r)
	}

	return repos, total, nil
}

// Update updates a repository
func (s *RepositoryStore) Update(ctx context.Context, orgID, repoID uuid.UUID, input *models.UpdateRepositoryInput) (*models.Repository, error) {
	var updates []string
	var args []interface{}
	argNum := 1

	if input.Name != nil {
		updates = append(updates, fmt.Sprintf("name = $%d", argNum))
		args = append(args, *input.Name)
		argNum++
	}

	if input.URL != nil {
		updates = append(updates, fmt.Sprintf("url = $%d", argNum))
		args = append(args, *input.URL)
		argNum++
	}

	if input.Provider != nil {
		updates = append(updates, fmt.Sprintf("provider = $%d", argNum))
		args = append(args, *input.Provider)
		argNum++
	}

	if input.OwnerUserID != nil {
		updates = append(updates, fmt.Sprintf("owner_user_id = $%d", argNum))
		args = append(args, *input.OwnerUserID)
		argNum++
	}

	if input.OwnerGroupID != nil {
		updates = append(updates, fmt.Sprintf("owner_group_id = $%d", argNum))
		args = append(args, *input.OwnerGroupID)
		argNum++
	}

	if input.IsActive != nil {
		updates = append(updates, fmt.Sprintf("is_active = $%d", argNum))
		args = append(args, *input.IsActive)
		argNum++
	}

	if input.IsPrivate != nil {
		updates = append(updates, fmt.Sprintf("is_private = $%d", argNum))
		args = append(args, *input.IsPrivate)
		argNum++
	}

	if input.Description != nil {
		updates = append(updates, fmt.Sprintf("description = $%d", argNum))
		args = append(args, *input.Description)
		argNum++
	}

	if len(updates) == 0 {
		return s.GetByID(ctx, orgID, repoID)
	}

	updates = append(updates, "updated_at = NOW()")

	query := fmt.Sprintf(
		"UPDATE repositories SET %s WHERE id = $%d AND organization_id = $%d",
		strings.Join(updates, ", "), argNum, argNum+1,
	)
	args = append(args, repoID, orgID)

	_, err := s.db.ExecContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to update repository: %w", err)
	}

	return s.GetByID(ctx, orgID, repoID)
}

// Delete deactivates a repository
func (s *RepositoryStore) Delete(ctx context.Context, orgID, repoID uuid.UUID) error {
	query := "UPDATE repositories SET is_active = false, updated_at = NOW() WHERE id = $1 AND organization_id = $2"
	_, err := s.db.ExecContext(ctx, query, repoID, orgID)
	return err
}

// GetTicketRepositories retrieves repositories linked to a ticket
func (s *RepositoryStore) GetTicketRepositories(ctx context.Context, ticketID uuid.UUID) ([]models.TicketRepository, error) {
	query := `
		SELECT tr.id, tr.ticket_id, tr.repository_id, tr.linked_by, tr.link_type,
		       tr.branch_name, tr.commit_sha, tr.pr_number, tr.notes, tr.created_at,
		       r.name, r.url, r.provider, r.is_active
		FROM ticket_repositories tr
		JOIN repositories r ON tr.repository_id = r.id
		WHERE tr.ticket_id = $1
		ORDER BY tr.created_at DESC
	`

	rows, err := s.db.QueryContext(ctx, query, ticketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get ticket repositories: %w", err)
	}
	defer rows.Close()

	var repos []models.TicketRepository
	for rows.Next() {
		var tr models.TicketRepository
		var repoSummary models.RepositorySummary
		err := rows.Scan(
			&tr.ID, &tr.TicketID, &tr.RepositoryID, &tr.LinkedBy, &tr.LinkType,
			&tr.BranchName, &tr.CommitSHA, &tr.PRNumber, &tr.Notes, &tr.CreatedAt,
			&repoSummary.Name, &repoSummary.URL, &repoSummary.Provider, &repoSummary.IsActive,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan ticket repository: %w", err)
		}
		repoSummary.ID = tr.RepositoryID
		tr.Repository = &repoSummary
		repos = append(repos, tr)
	}

	return repos, nil
}
