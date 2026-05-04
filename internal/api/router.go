package api

import (
	"net/http"
	"time"

	"github.com/afterdarksys/adsops-utils/internal/api/handlers"
	"github.com/afterdarksys/adsops-utils/internal/api/middleware"
	"github.com/afterdarksys/adsops-utils/internal/config"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// NewRouter creates and configures the Gin router
func NewRouter(cfg *config.Config, logger *zap.Logger) *gin.Engine {
	// Set Gin mode based on environment
	if cfg.Environment == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()

	// Global middleware
	router.Use(middleware.RequestID())
	router.Use(middleware.Logger(logger))
	router.Use(middleware.Recovery(logger))
	router.Use(middleware.CORS(cfg))
	router.Use(middleware.RateLimit())
	router.Use(middleware.SecurityHeaders())

	// API documentation at root
	router.GET("/", handlers.APIDocumentation)

	// Health endpoints (no auth required)
	router.GET("/health", handlers.Health)
	router.GET("/health/ready", handlers.Ready)

	// API v1 routes
	v1 := router.Group("/v1")
	{
		// Authentication routes (public)
		auth := v1.Group("/auth")
		{
			auth.POST("/login", handlers.Login)
			auth.POST("/login/mfa", handlers.LoginMFA)
			auth.POST("/login/oauth2/google", handlers.LoginOAuth2Google)
			auth.POST("/login/oauth2/afterdark", handlers.LoginOAuth2AfterDark)
			auth.POST("/login/passkey/begin", handlers.LoginPasskeyBegin)
			auth.POST("/login/passkey/finish", handlers.LoginPasskeyFinish)
			auth.POST("/refresh", handlers.RefreshToken)
		}

		// Token-based approval routes (public with token validation)
		v1.POST("/approvals/token/:token/approve", handlers.ApproveByToken)
		v1.POST("/approvals/token/:token/deny", handlers.DenyByToken)
		v1.GET("/approvals/token/:token", handlers.GetApprovalByToken)

		// Protected routes (require authentication)
		protected := v1.Group("")
		protected.Use(middleware.Auth(cfg))
		{
			// Current user
			protected.GET("/auth/me", handlers.GetCurrentUser)
			protected.POST("/auth/logout", handlers.Logout)

			// Tickets
			tickets := protected.Group("/tickets")
			{
				tickets.POST("", handlers.CreateTicket)
				tickets.GET("", handlers.ListTickets)
				tickets.GET("/:id", handlers.GetTicket)
				tickets.PATCH("/:id", handlers.UpdateTicket)
				tickets.POST("/:id/submit", handlers.SubmitTicket)
				tickets.POST("/:id/cancel", handlers.CancelTicket)
				tickets.POST("/:id/close", handlers.CloseTicket)
				tickets.POST("/:id/reopen", handlers.ReopenTicket)
				tickets.GET("/:id/revisions", handlers.GetTicketRevisions)
				tickets.GET("/:id/audit", handlers.GetTicketAudit)

				// Comments
				tickets.POST("/:id/comments", handlers.CreateComment)
				tickets.GET("/:id/comments", handlers.ListComments)
			}

			// Comments (for editing/deleting by ID)
			comments := protected.Group("/comments")
			{
				comments.PATCH("/:id", handlers.UpdateComment)
				comments.DELETE("/:id", handlers.DeleteComment)
			}

			// Approvals
			approvals := protected.Group("/approvals")
			{
				approvals.GET("", handlers.ListApprovals)
				approvals.GET("/:id", handlers.GetApproval)
				approvals.POST("/:id/approve", handlers.Approve)
				approvals.POST("/:id/deny", handlers.Deny)
				approvals.POST("/:id/request-update", handlers.RequestUpdate)
			}

			// Users (admin only)
			users := protected.Group("/users")
			users.Use(middleware.RequireRole("admin"))
			{
				users.GET("", handlers.ListUsers)
				users.POST("", handlers.CreateUser)
				users.GET("/:id", handlers.GetUser)
				users.PATCH("/:id", handlers.UpdateUser)
				users.DELETE("/:id", handlers.DeleteUser)
				users.POST("/:id/reset-password", handlers.ResetUserPassword)
				users.POST("/:id/enable-mfa", handlers.EnableUserMFA)
				users.POST("/:id/disable-mfa", handlers.DisableUserMFA)
			}

			// Compliance & Reporting
			compliance := protected.Group("/compliance")
			{
				compliance.GET("/frameworks", handlers.ListComplianceFrameworks)
				compliance.GET("/templates", handlers.ListComplianceTemplates)
				compliance.POST("/templates", handlers.CreateComplianceTemplate)
			}

			reports := protected.Group("/reports")
			reports.Use(middleware.RequireRole("admin", "auditor"))
			{
				reports.GET("/audit", handlers.AuditReport)
				reports.GET("/compliance/:framework", handlers.ComplianceReport)
				reports.GET("/user-activity/:user_id", handlers.UserActivityReport)
			}

			// Agents
			agents := protected.Group("/agents")
			{
				agents.GET("", handlers.ListAgents)
				agents.GET("/:agent_id", handlers.GetAgent)
				agents.GET("/:agent_id/tickets", handlers.GetAgentTickets)
				agents.POST("/:agent_id/notify", handlers.NotifyAgent)
				agents.GET("/:agent_id/activity", handlers.GetAgentActivity)
				agents.POST("/tokens", handlers.IssueAgentToken)
				agents.DELETE("/tokens/:token_id", handlers.RevokeAgentToken)
			}

			// Infrastructure (admin or operator only)
			infra := protected.Group("/infra")
			infra.Use(middleware.RequireRole("admin", "operator"))
			{
				// Docker
				docker := infra.Group("/docker")
				{
					docker.GET("/containers", handlers.ListContainers)
					docker.GET("/containers/:id/logs", handlers.GetContainerLogs)
					docker.POST("/containers/:id/:action", handlers.ContainerAction)
				}

				// Kubernetes
				k8s := infra.Group("/k8s")
				{
					k8s.GET("/pods", handlers.ListPods)
					k8s.GET("/deployments", handlers.ListDeployments)
					k8s.POST("/deployments/:name/scale", handlers.ScaleDeployment)
					k8s.GET("/pods/:name/logs", handlers.GetPodLogs)
				}

				// System
				system := infra.Group("/system")
				{
					system.GET("/metrics", handlers.GetSystemMetrics)
				}
			}
		}
	}

	// Metrics endpoint (internal only)
	router.GET("/metrics", middleware.InternalOnly(), handlers.Metrics)

	// 404 handler
	router.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{
			"error": gin.H{
				"code":      "NOT_FOUND",
				"message":   "The requested resource was not found",
				"timestamp": time.Now().UTC().Format(time.RFC3339),
			},
		})
	})

	return router
}
