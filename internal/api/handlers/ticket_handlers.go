package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/adsops-utils/internal/models"
	"github.com/adsops-utils/internal/store"
)

// TicketHandler handles ticket-related HTTP requests
type TicketHandler struct {
	store *store.Store
}

// NewTicketHandler creates a new ticket handler
func NewTicketHandler(s *store.Store) *TicketHandler {
	return &TicketHandler{store: s}
}

// CreateTicket handles POST /api/v1/tickets
func (h *TicketHandler) CreateTicket(c *gin.Context) {
	var input models.CreateTicketInput
	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Get user and org from context (set by auth middleware)
	userID, _ := c.Get("user_id")
	orgID, _ := c.Get("org_id")

	ticket, err := h.store.Tickets.Create(c.Request.Context(), orgID.(uuid.UUID), userID.(uuid.UUID), &input)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Log audit
	h.store.Audit.LogTicketAccess(c.Request.Context(), ticket.ID, userID.(uuid.UUID), "create", nil, nil, nil)

	// Submit if requested
	if input.Submit {
		if err := h.store.Tickets.Submit(c.Request.Context(), orgID.(uuid.UUID), ticket.ID); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "ticket created but failed to submit: " + err.Error()})
			return
		}
		ticket.Status = models.TicketStatusSubmitted
	}

	c.JSON(http.StatusCreated, gin.H{
		"ticket": ticket,
	})
}

// ListTickets handles GET /api/v1/tickets
func (h *TicketHandler) ListTickets(c *gin.Context) {
	orgID, _ := c.Get("org_id")

	// Parse filter from query params
	filter := &models.TicketListFilter{}

	if status := c.Query("status"); status != "" {
		filter.Status = []models.TicketStatus{models.TicketStatus(status)}
	}
	if priority := c.Query("priority"); priority != "" {
		filter.Priority = []models.TicketPriority{models.TicketPriority(priority)}
	}
	if search := c.Query("search"); search != "" {
		filter.Search = search
	}
	if projectID := c.Query("project_id"); projectID != "" {
		if uid, err := uuid.Parse(projectID); err == nil {
			filter.ProjectID = &uid
		}
	}
	if c.Query("needs_assignment") == "true" {
		filter.NeedsAssignment = true
	}

	filter.Page = 1
	filter.PerPage = 50

	tickets, total, err := h.store.Tickets.List(c.Request.Context(), orgID.(uuid.UUID), filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tickets": tickets,
		"total":   total,
		"page":    filter.Page,
		"per_page": filter.PerPage,
	})
}

// GetTicket handles GET /api/v1/tickets/:id
func (h *TicketHandler) GetTicket(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	ticket, err := h.store.Tickets.GetByID(c.Request.Context(), orgID.(uuid.UUID), ticketID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "ticket not found"})
		return
	}

	// Log view
	h.store.Audit.LogTicketView(c.Request.Context(), ticketID, userID.(uuid.UUID), nil, nil)

	// Get linked repositories
	repos, _ := h.store.Repositories.GetTicketRepositories(c.Request.Context(), ticketID)
	ticket.Repositories = repos

	c.JSON(http.StatusOK, gin.H{
		"ticket": ticket,
	})
}

// UpdateTicket handles PATCH /api/v1/tickets/:id
func (h *TicketHandler) UpdateTicket(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	var input models.UpdateTicketInput
	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ticket, err := h.store.Tickets.Update(c.Request.Context(), orgID.(uuid.UUID), ticketID, &input)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Log audit
	h.store.Audit.LogTicketEdit(c.Request.Context(), ticketID, userID.(uuid.UUID), nil, nil, nil)

	c.JSON(http.StatusOK, gin.H{
		"ticket": ticket,
	})
}

// SubmitTicket handles POST /api/v1/tickets/:id/submit
func (h *TicketHandler) SubmitTicket(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	if err := h.store.Tickets.Submit(c.Request.Context(), orgID.(uuid.UUID), ticketID); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Log status change
	h.store.Audit.LogTicketStatusChange(c.Request.Context(), ticketID, userID.(uuid.UUID), "draft", "submitted", nil, nil)

	c.JSON(http.StatusOK, gin.H{
		"message": "Ticket submitted for approval",
	})
}

// CancelTicket handles POST /api/v1/tickets/:id/cancel
func (h *TicketHandler) CancelTicket(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	var input struct {
		Reason string `json:"reason"`
	}
	c.ShouldBindJSON(&input)

	if err := h.store.Tickets.Cancel(c.Request.Context(), orgID.(uuid.UUID), ticketID, input.Reason); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Log status change
	h.store.Audit.LogTicketStatusChange(c.Request.Context(), ticketID, userID.(uuid.UUID), "", "cancelled", nil, nil)

	c.JSON(http.StatusOK, gin.H{
		"message": "Ticket cancelled",
	})
}

// CloseTicket handles POST /api/v1/tickets/:id/close
func (h *TicketHandler) CloseTicket(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	if err := h.store.Tickets.Close(c.Request.Context(), orgID.(uuid.UUID), ticketID); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Log status change
	h.store.Audit.LogTicketStatusChange(c.Request.Context(), ticketID, userID.(uuid.UUID), "completed", "closed", nil, nil)

	c.JSON(http.StatusOK, gin.H{
		"message": "Ticket closed",
	})
}

// ReopenTicket handles POST /api/v1/tickets/:id/reopen
func (h *TicketHandler) ReopenTicket(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	if err := h.store.Tickets.UpdateStatus(c.Request.Context(), orgID.(uuid.UUID), ticketID, models.TicketStatusUpdateRequested); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Log status change
	h.store.Audit.LogTicketStatusChange(c.Request.Context(), ticketID, userID.(uuid.UUID), "closed", "update_requested", nil, nil)

	c.JSON(http.StatusOK, gin.H{
		"message": "Ticket reopened",
	})
}

// GetTicketRevisions handles GET /api/v1/tickets/:id/revisions
func (h *TicketHandler) GetTicketRevisions(c *gin.Context) {
	// Return audit log for this ticket
	orgID, _ := c.Get("org_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	// Verify ticket exists
	_, err = h.store.Tickets.GetByID(c.Request.Context(), orgID.(uuid.UUID), ticketID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "ticket not found"})
		return
	}

	filter := &models.AuditLogFilter{}
	logs, total, err := h.store.Audit.GetTicketAuditLog(c.Request.Context(), ticketID, filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"revisions": logs,
		"total":     total,
	})
}

// GetTicketAudit handles GET /api/v1/tickets/:id/audit
func (h *TicketHandler) GetTicketAudit(c *gin.Context) {
	// Alias for GetTicketRevisions
	h.GetTicketRevisions(c)
}

// AssignTicket handles POST /api/v1/tickets/:id/assign
func (h *TicketHandler) AssignTicket(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	var input struct {
		AssigneeID uuid.UUID `json:"assignee_id" binding:"required"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.store.Tickets.Assign(c.Request.Context(), orgID.(uuid.UUID), ticketID, input.AssigneeID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Log assignment
	changes := map[string]interface{}{"assigned_to": input.AssigneeID.String()}
	h.store.Audit.LogTicketAccess(c.Request.Context(), ticketID, userID.(uuid.UUID), "assign", nil, nil, changes)

	c.JSON(http.StatusOK, gin.H{
		"message": "Ticket assigned",
	})
}

// GetTicketQueue handles GET /api/v1/tickets/queue
func (h *TicketHandler) GetTicketQueue(c *gin.Context) {
	orgID, _ := c.Get("org_id")

	tickets, err := h.store.Tickets.GetQueue(c.Request.Context(), orgID.(uuid.UUID))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"queue":   tickets,
		"count":   len(tickets),
	})
}

// LinkRepository handles POST /api/v1/tickets/:id/repositories
func (h *TicketHandler) LinkRepository(c *gin.Context) {
	orgID, _ := c.Get("org_id")
	userID, _ := c.Get("user_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	// Check if linking by URL or by ID
	var input struct {
		RepositoryID *uuid.UUID `json:"repository_id"`
		URL          string     `json:"url"`
		LinkType     string     `json:"link_type"`
		BranchName   *string    `json:"branch_name"`
		Notes        *string    `json:"notes"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var repoID uuid.UUID
	if input.RepositoryID != nil {
		repoID = *input.RepositoryID
	} else if input.URL != "" {
		// Find or create repository by URL
		repo, err := h.store.Repositories.GetByURL(c.Request.Context(), orgID.(uuid.UUID), input.URL)
		if err != nil {
			// Create new repository
			createInput := &models.CreateRepositoryInput{
				Name:     input.URL, // Will be updated later
				URL:      input.URL,
				Provider: guessProvider(input.URL),
			}
			repo, err = h.store.Repositories.Create(c.Request.Context(), orgID.(uuid.UUID), createInput)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}
		}
		repoID = repo.ID
	} else {
		c.JSON(http.StatusBadRequest, gin.H{"error": "repository_id or url is required"})
		return
	}

	linkInput := &models.LinkRepositoryInput{
		RepositoryID: repoID,
		LinkType:     input.LinkType,
		BranchName:   input.BranchName,
		Notes:        input.Notes,
	}

	if err := h.store.Tickets.LinkRepository(c.Request.Context(), ticketID, repoID, userID.(uuid.UUID), linkInput); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Repository linked",
	})
}

// UnlinkRepository handles DELETE /api/v1/tickets/:id/repositories/:repo_id
func (h *TicketHandler) UnlinkRepository(c *gin.Context) {
	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	repoID, err := uuid.Parse(c.Param("repo_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository ID"})
		return
	}

	if err := h.store.Tickets.UnlinkRepository(c.Request.Context(), ticketID, repoID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Repository unlinked",
	})
}

// AddWatcher handles POST /api/v1/tickets/:id/watchers
func (h *TicketHandler) AddWatcher(c *gin.Context) {
	orgID, _ := c.Get("org_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	var input struct {
		UserID uuid.UUID `json:"user_id" binding:"required"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.store.Tickets.AddWatcher(c.Request.Context(), orgID.(uuid.UUID), ticketID, input.UserID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Watcher added",
	})
}

// RemoveWatcher handles DELETE /api/v1/tickets/:id/watchers/:user_id
func (h *TicketHandler) RemoveWatcher(c *gin.Context) {
	orgID, _ := c.Get("org_id")

	ticketID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ticket ID"})
		return
	}

	watcherID, err := uuid.Parse(c.Param("user_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user ID"})
		return
	}

	if err := h.store.Tickets.RemoveWatcher(c.Request.Context(), orgID.(uuid.UUID), ticketID, watcherID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Watcher removed",
	})
}

func guessProvider(url string) models.RepositoryProvider {
	if contains(url, "github.com") {
		return models.RepositoryProviderGitHub
	}
	if contains(url, "gitlab.com") {
		return models.RepositoryProviderGitLab
	}
	if contains(url, "bitbucket.org") {
		return models.RepositoryProviderBitbucket
	}
	if contains(url, "dev.azure.com") || contains(url, "visualstudio.com") {
		return models.RepositoryProviderAzureDevOps
	}
	return models.RepositoryProviderGitHub
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsCheck(s, substr))
}

func containsCheck(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
