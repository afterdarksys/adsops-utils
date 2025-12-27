package store

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/google/uuid"
	"github.com/adsops-utils/internal/models"
)

// ProjectStore handles project database operations
type ProjectStore struct {
	db *sql.DB
}

// Create creates a new project
func (s *ProjectStore) Create(ctx context.Context, orgID, createdBy uuid.UUID, input *models.CreateProjectInput) (*models.Project, error) {
	project := &models.Project{
		ID:                uuid.New(),
		OrganizationID:    orgID,
		ProjectKey:        input.ProjectKey,
		Name:              input.Name,
		Description:       input.Description,
		LeadUserID:        input.LeadUserID,
		DefaultAssigneeID: input.DefaultAssigneeID,
		OwningGroupID:     input.OwningGroupID,
		CustomerID:        input.CustomerID,
		IsActive:          true,
		IconURL:           input.IconURL,
		CreatedBy:         &createdBy,
	}

	query := `
		INSERT INTO projects (
			id, organization_id, project_key, name, description, lead_user_id,
			default_assignee_id, owning_group_id, customer_id, is_active, icon_url, created_by
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`

	_, err := s.db.ExecContext(ctx, query,
		project.ID, project.OrganizationID, project.ProjectKey, project.Name,
		project.Description, project.LeadUserID, project.DefaultAssigneeID,
		project.OwningGroupID, project.CustomerID, project.IsActive,
		project.IconURL, project.CreatedBy,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create project: %w", err)
	}

	return project, nil
}

// GetByID retrieves a project by ID
func (s *ProjectStore) GetByID(ctx context.Context, orgID, projectID uuid.UUID) (*models.Project, error) {
	query := `
		SELECT id, organization_id, project_key, name, description, lead_user_id,
		       default_assignee_id, owning_group_id, customer_id, is_active, icon_url,
		       created_at, updated_at, created_by
		FROM projects
		WHERE id = $1 AND organization_id = $2
	`

	project := &models.Project{}
	err := s.db.QueryRowContext(ctx, query, projectID, orgID).Scan(
		&project.ID, &project.OrganizationID, &project.ProjectKey, &project.Name,
		&project.Description, &project.LeadUserID, &project.DefaultAssigneeID,
		&project.OwningGroupID, &project.CustomerID, &project.IsActive, &project.IconURL,
		&project.CreatedAt, &project.UpdatedAt, &project.CreatedBy,
	)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("project not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get project: %w", err)
	}

	return project, nil
}

// GetByKey retrieves a project by key
func (s *ProjectStore) GetByKey(ctx context.Context, orgID uuid.UUID, key string) (*models.Project, error) {
	var projectID uuid.UUID
	err := s.db.QueryRowContext(ctx,
		"SELECT id FROM projects WHERE organization_id = $1 AND project_key = $2",
		orgID, key,
	).Scan(&projectID)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("project not found")
	}
	if err != nil {
		return nil, err
	}
	return s.GetByID(ctx, orgID, projectID)
}

// List retrieves all active projects
func (s *ProjectStore) List(ctx context.Context, orgID uuid.UUID, activeOnly bool) ([]models.Project, error) {
	query := `
		SELECT id, organization_id, project_key, name, description, lead_user_id,
		       default_assignee_id, owning_group_id, customer_id, is_active, icon_url,
		       created_at, updated_at
		FROM projects
		WHERE organization_id = $1
	`
	if activeOnly {
		query += " AND is_active = true"
	}
	query += " ORDER BY name"

	rows, err := s.db.QueryContext(ctx, query, orgID)
	if err != nil {
		return nil, fmt.Errorf("failed to list projects: %w", err)
	}
	defer rows.Close()

	var projects []models.Project
	for rows.Next() {
		var p models.Project
		err := rows.Scan(
			&p.ID, &p.OrganizationID, &p.ProjectKey, &p.Name, &p.Description,
			&p.LeadUserID, &p.DefaultAssigneeID, &p.OwningGroupID, &p.CustomerID,
			&p.IsActive, &p.IconURL, &p.CreatedAt, &p.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan project: %w", err)
		}
		projects = append(projects, p)
	}

	return projects, nil
}

// Update updates a project
func (s *ProjectStore) Update(ctx context.Context, orgID, projectID uuid.UUID, input *models.UpdateProjectInput) (*models.Project, error) {
	// Build update query dynamically - simplified version
	query := `
		UPDATE projects SET
			name = COALESCE($3, name),
			description = COALESCE($4, description),
			lead_user_id = COALESCE($5, lead_user_id),
			default_assignee_id = COALESCE($6, default_assignee_id),
			updated_at = NOW()
		WHERE id = $1 AND organization_id = $2
	`
	_, err := s.db.ExecContext(ctx, query,
		projectID, orgID, input.Name, input.Description,
		input.LeadUserID, input.DefaultAssigneeID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to update project: %w", err)
	}

	return s.GetByID(ctx, orgID, projectID)
}

// Delete deactivates a project
func (s *ProjectStore) Delete(ctx context.Context, orgID, projectID uuid.UUID) error {
	query := "UPDATE projects SET is_active = false, updated_at = NOW() WHERE id = $1 AND organization_id = $2"
	_, err := s.db.ExecContext(ctx, query, projectID, orgID)
	return err
}
