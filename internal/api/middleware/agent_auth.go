package middleware

import (
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// AgentAuth validates long-lived agent API tokens (format: "agt_<random>").
// Tokens are resolved to an Agent principal and set into gin context so that
// RequireRole works identically for both human users and agents.
func AgentAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": gin.H{
					"code":      "UNAUTHORIZED",
					"message":   "Authorization header is required",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				},
			})
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": gin.H{
					"code":      "INVALID_TOKEN_FORMAT",
					"message":   "Authorization header must be in 'Bearer <token>' format",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				},
			})
			return
		}

		token := parts[1]
		if !strings.HasPrefix(token, "agt_") {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": gin.H{
					"code":      "INVALID_TOKEN_FORMAT",
					"message":   "Agent tokens must begin with 'agt_'",
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				},
			})
			return
		}

		// TODO: Replace placeholder with real DB lookup:
		//   1. Hash token with sha256 (fast pre-filter), query agent_tokens WHERE token_hash = $1
		//   2. bcrypt.CompareHashAndPassword(row.TokenHash, []byte(token))
		//   3. Check row.RevokedAt IS NULL and (row.ExpiresAt IS NULL OR row.ExpiresAt > NOW())
		//   4. JOIN agents WHERE id = row.AgentID AND active = TRUE
		//   5. Set context values from agent row
		_ = token
		c.Set("user_id", "agent-placeholder")
		c.Set("principal_type", "agent")
		c.Set("principal_id", "agent-placeholder")
		c.Set("agent_id", "unknown")
		c.Set("roles", []string{"viewer"})

		c.Next()
	}
}
