package handlers

import (
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/lib/pq"
	"golang.org/x/crypto/bcrypt"
)

// APIKeyHandler handles API key-related HTTP requests
type APIKeyHandler struct {
	db *sql.DB
}

// NewAPIKeyHandler creates a new API key handler
func NewAPIKeyHandler(db *sql.DB) *APIKeyHandler {
	return &APIKeyHandler{db: db}
}

// CreateAPIKeyInput represents the request to create an API key
type CreateAPIKeyInput struct {
	Name      string   `json:"name" binding:"required,min=1,max=255"`
	Scopes    []string `json:"scopes"`
	ExpiresIn *int     `json:"expires_in"` // Days until expiration (null = never)
}

// APIKeyResponse represents an API key in responses
type APIKeyResponse struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	KeyPrefix   string    `json:"key_prefix"`
	Scopes      []string  `json:"scopes"`
	CreatedAt   time.Time `json:"created_at"`
	ExpiresAt   *time.Time `json:"expires_at,omitempty"`
	LastUsedAt  *time.Time `json:"last_used_at,omitempty"`
	UsageCount  int64     `json:"usage_count"`
	IsActive    bool      `json:"is_active"`
}

// CreateAPIKeyResponse includes the actual key (only shown once)
type CreateAPIKeyResponse struct {
	APIKeyResponse
	APIKey string `json:"api_key"` // Full key - only shown on creation!
}

// CreateAPIKey handles POST /v1/api-keys
func (h *APIKeyHandler) CreateAPIKey(c *gin.Context) {
	userID := c.MustGet("user_id").(uuid.UUID)
	orgID := c.MustGet("org_id").(uuid.UUID)

	var input CreateAPIKeyInput
	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": gin.H{
				"code":    "VALIDATION_ERROR",
				"message": err.Error(),
			},
		})
		return
	}

	// Default scopes if not provided
	if len(input.Scopes) == 0 {
		input.Scopes = []string{"tickets:read", "tickets:write"}
	}

	// Generate cryptographically secure API key
	apiKey, keyHash, keyPrefix, err := generateAPIKey()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": gin.H{
				"code":    "KEY_GENERATION_ERROR",
				"message": "Failed to generate API key",
			},
		})
		return
	}

	// Calculate expiration
	var expiresAt *time.Time
	if input.ExpiresIn != nil && *input.ExpiresIn > 0 {
		exp := time.Now().AddDate(0, 0, *input.ExpiresIn)
		expiresAt = &exp
	}

	// Insert into database
	var keyID uuid.UUID
	var createdAt time.Time

	query := `
		INSERT INTO api_keys (
			user_id, organization_id, name, key_hash, key_prefix,
			scopes, expires_at, created_ip
		)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING id, created_at
	`

	err = h.db.QueryRowContext(
		c.Request.Context(),
		query,
		userID, orgID, input.Name, keyHash, keyPrefix,
		input.Scopes, expiresAt, c.ClientIP(),
	).Scan(&keyID, &createdAt)

	if err != nil {
		// Check if it's the 5-key limit error
		if err.Error() == "pq: Maximum of 5 active API keys per user. Please revoke an existing key first." {
			c.JSON(http.StatusForbidden, gin.H{
				"error": gin.H{
					"code":    "KEY_LIMIT_EXCEEDED",
					"message": "You have reached the maximum of 5 active API keys. Please delete an existing key first.",
				},
			})
			return
		}

		c.JSON(http.StatusInternalServerError, gin.H{
			"error": gin.H{
				"code":    "DATABASE_ERROR",
				"message": "Failed to create API key",
			},
		})
		return
	}

	c.JSON(http.StatusCreated, CreateAPIKeyResponse{
		APIKeyResponse: APIKeyResponse{
			ID:         keyID.String(),
			Name:       input.Name,
			KeyPrefix:  keyPrefix,
			Scopes:     input.Scopes,
			CreatedAt:  createdAt,
			ExpiresAt:  expiresAt,
			UsageCount: 0,
			IsActive:   true,
		},
		APIKey: apiKey, // Full key - only shown this once!
	})
}

// ListAPIKeys handles GET /v1/api-keys
func (h *APIKeyHandler) ListAPIKeys(c *gin.Context) {
	userID := c.MustGet("user_id").(uuid.UUID)
	orgID := c.MustGet("org_id").(uuid.UUID)

	query := `
		SELECT
			id, name, key_prefix, scopes, created_at, expires_at,
			last_used_at, usage_count, is_active
		FROM api_keys
		WHERE user_id = $1 AND organization_id = $2
		  AND revoked_at IS NULL
		ORDER BY created_at DESC
	`

	rows, err := h.db.QueryContext(c.Request.Context(), query, userID, orgID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": gin.H{
				"code":    "DATABASE_ERROR",
				"message": "Failed to list API keys",
			},
		})
		return
	}
	defer rows.Close()

	keys := []APIKeyResponse{}
	for rows.Next() {
		var key APIKeyResponse
		var scopes []string
		var id string

		err := rows.Scan(
			&id, &key.Name, &key.KeyPrefix, pq.Array(&scopes),
			&key.CreatedAt, &key.ExpiresAt, &key.LastUsedAt,
			&key.UsageCount, &key.IsActive,
		)
		if err != nil {
			continue
		}

		key.ID = id
		key.Scopes = scopes
		keys = append(keys, key)
	}

	c.JSON(http.StatusOK, gin.H{
		"keys":  keys,
		"total": len(keys),
		"limit": 5,
	})
}

// DeleteAPIKey handles DELETE /v1/api-keys/:id
func (h *APIKeyHandler) DeleteAPIKey(c *gin.Context) {
	userID := c.MustGet("user_id").(uuid.UUID)
	orgID := c.MustGet("org_id").(uuid.UUID)
	keyID := c.Param("id")

	// Verify key belongs to user and mark as revoked
	query := `
		UPDATE api_keys
		SET
			revoked_at = NOW(),
			revoked_by = $1,
			revoke_reason = 'User requested deletion',
			is_active = false,
			updated_at = NOW()
		WHERE id = $2 AND user_id = $1 AND organization_id = $3
		  AND revoked_at IS NULL
		RETURNING id
	`

	var deletedID string
	err := h.db.QueryRowContext(c.Request.Context(), query, userID, keyID, orgID).Scan(&deletedID)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{
			"error": gin.H{
				"code":    "KEY_NOT_FOUND",
				"message": "API key not found or already deleted",
			},
		})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": gin.H{
				"code":    "DATABASE_ERROR",
				"message": "Failed to delete API key",
			},
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "API key deleted successfully",
		"id":      deletedID,
	})
}

// generateAPIKey creates a new API key with format: chg_<32 random bytes in base64>
func generateAPIKey() (apiKey, keyHash, keyPrefix string, err error) {
	// Generate 32 random bytes
	randomBytes := make([]byte, 32)
	if _, err := rand.Read(randomBytes); err != nil {
		return "", "", "", err
	}

	// Encode to base64url (URL-safe, no padding)
	encoded := base64.RawURLEncoding.EncodeToString(randomBytes)

	// Format: chg_<encoded>
	apiKey = "chg_" + encoded

	// Extract prefix (first 16 chars including "chg_")
	keyPrefix = apiKey
	if len(apiKey) > 16 {
		keyPrefix = apiKey[:16]
	}

	// Hash the full key for storage
	hash, err := bcrypt.GenerateFromPassword([]byte(apiKey), bcrypt.DefaultCost)
	if err != nil {
		return "", "", "", err
	}

	return apiKey, string(hash), keyPrefix, nil
}
