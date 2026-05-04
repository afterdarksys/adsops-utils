package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// ListAgents returns all registered agents.
// TODO: Query agents table, return paginated list of Agent records.
func ListAgents(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// GetAgent returns a single agent by agent_id (human-readable slug, e.g. "kai_nakamura").
// TODO: Query agents WHERE agent_id = :agent_id.
func GetAgent(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// GetAgentTickets returns tickets assigned to the agent.
// TODO: Query tickets WHERE assigned_to = agent.ID AND assigned_to_type = 'agent'.
func GetAgentTickets(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// NotifyAgent forwards an event to the agent's webhook URL.
// Accepts body: {event: string, payload: object}
// TODO:
//  1. Look up agent by :agent_id, check agent.WebhookURL is set
//  2. POST {event, payload} to agent.WebhookURL with 10s timeout
//  3. Return 200 on success, 502 on upstream failure, 404 if no webhook configured
func NotifyAgent(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// GetAgentActivity returns a recent activity log for the agent.
// TODO: Query audit_log WHERE actor_id = agent.ID ORDER BY created_at DESC LIMIT 100.
func GetAgentActivity(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// IssueAgentToken creates a new long-lived API token for an agent.
// Accepts body: {agent_id: string, label: string, expires_in_days: int (optional)}
// Token issuance flow (implement when DB is wired):
//  1. Validate body — agent_id and label required; expires_in_days optional (0 = non-expiring)
//  2. Look up agent by agent_id, 404 if not found
//  3. Generate 32 random bytes via crypto/rand, hex-encode, prefix "agt_" → rawToken
//  4. bcrypt.GenerateFromPassword([]byte(rawToken), bcrypt.DefaultCost) → tokenHash
//  5. INSERT INTO agent_tokens (agent_id, token_hash, label, expires_at) VALUES (...)
//  6. Return {token_id: uuid, token: rawToken} — raw token shown ONCE, never stored again
func IssueAgentToken(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// RevokeAgentToken marks a token as revoked (soft delete via revoked_at timestamp).
// TODO: UPDATE agent_tokens SET revoked_at = NOW() WHERE id = :token_id.
// Returns 404 if token not found, 409 if already revoked.
func RevokeAgentToken(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}
