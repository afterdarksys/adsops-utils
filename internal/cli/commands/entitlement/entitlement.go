package entitlement

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

// API endpoints
const (
	defaultAPIURL = "https://billing.afterdarksys.com"
)

// AuthConfig represents stored auth configuration
type AuthConfig struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	ExpiresAt    time.Time `json:"expires_at"`
	Email        string    `json:"email"`
	UserID       string    `json:"user_id"`
	IsAdmin      bool      `json:"is_admin"`
}

// Entitlement represents a user entitlement
type Entitlement struct {
	ProductCode string            `json:"productCode"`
	ProductName string            `json:"productName"`
	Domain      string            `json:"domain"`
	Tier        string            `json:"tier"`
	Features    []string          `json:"features"`
	Limits      map[string]int    `json:"limits"`
	ExpiresAt   *time.Time        `json:"expiresAt"`
	Source      string            `json:"source"`
}

// EntitlementGrant represents an admin-granted entitlement
type EntitlementGrant struct {
	ID          string     `json:"id"`
	UserID      string     `json:"userId"`
	ProductCode string     `json:"productCode"`
	GrantedBy   string     `json:"grantedBy"`
	Reason      string     `json:"reason"`
	ExpiresAt   *time.Time `json:"expiresAt"`
	CreatedAt   time.Time  `json:"createdAt"`
	RevokedAt   *time.Time `json:"revokedAt"`
}

// EntitlementCmd is the root command for entitlement management
var EntitlementCmd = &cobra.Command{
	Use:     "entitlement",
	Aliases: []string{"ent", "entitlements"},
	Short:   "Manage user entitlements across AfterDark domains",
	Long: `Manage user entitlements (product access, features, limits) across all domains
in the After Dark Systems portfolio.

Commands:
  login       Authenticate to the entitlements API
  logout      Clear stored credentials
  list        List entitlements for a user
  check       Check if user has access to a feature
  usage       View usage metrics for a user
  grant       Grant an entitlement to a user (admin)
  revoke      Revoke an entitlement grant (admin)
  approvers   List users who can approve entitlements
  users       List users for a domain/application
  log         View entitlement audit log

Authentication:
  The CLI stores credentials in ~/.adsops-utils/entitlements-auth.json
  You can also set ENTITLEMENTS_API_KEY environment variable`,
}

func init() {
	// Add subcommands
	EntitlementCmd.AddCommand(loginCmd)
	EntitlementCmd.AddCommand(logoutCmd)
	EntitlementCmd.AddCommand(listCmd)
	EntitlementCmd.AddCommand(checkCmd)
	EntitlementCmd.AddCommand(usageCmd)
	EntitlementCmd.AddCommand(grantCmd)
	EntitlementCmd.AddCommand(revokeCmd)
	EntitlementCmd.AddCommand(approversCmd)
	EntitlementCmd.AddCommand(usersCmd)
	EntitlementCmd.AddCommand(logCmd)
	EntitlementCmd.AddCommand(freezeCmd)
	EntitlementCmd.AddCommand(unfreezeCmd)
}

// ============================================
// LOGIN / LOGOUT
// ============================================

var loginCmd = &cobra.Command{
	Use:   "login",
	Short: "Authenticate to the entitlements API",
	Long: `Authenticate to the After Dark Systems entitlements API.

Examples:
  # Login interactively
  changes entitlement login

  # Login with email/password
  changes entitlement login --email admin@afterdarksys.com

  # Login with API key
  changes entitlement login --api-key YOUR_API_KEY`,
	Run: runLogin,
}

func init() {
	loginCmd.Flags().String("email", "", "Email address")
	loginCmd.Flags().String("api-key", "", "API key for service accounts")
}

func runLogin(cmd *cobra.Command, args []string) {
	apiKey, _ := cmd.Flags().GetString("api-key")
	email, _ := cmd.Flags().GetString("email")

	if apiKey != "" {
		// Validate API key by making a test request
		client := &http.Client{Timeout: 10 * time.Second}
		req, _ := http.NewRequest("GET", getAPIURL()+"/api/entitlements", nil)
		req.Header.Set("Authorization", "Bearer "+apiKey)

		resp, err := client.Do(req)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: Failed to connect to API: %v\n", err)
			os.Exit(1)
		}
		defer resp.Body.Close()

		if resp.StatusCode == 401 {
			fmt.Fprintln(os.Stderr, "Error: Invalid API key")
			os.Exit(1)
		}

		// Save auth config
		auth := AuthConfig{
			AccessToken: apiKey,
			ExpiresAt:   time.Now().Add(365 * 24 * time.Hour), // API keys don't expire
			IsAdmin:     true,
		}
		if err := saveAuthConfig(auth); err != nil {
			fmt.Fprintf(os.Stderr, "Error saving credentials: %v\n", err)
			os.Exit(1)
		}

		fmt.Println("Successfully authenticated with API key")
		return
	}

	// Interactive email/password login
	if email == "" {
		fmt.Print("Email: ")
		fmt.Scanln(&email)
	}

	fmt.Print("Password: ")
	var password string
	fmt.Scanln(&password)

	// Make login request
	client := &http.Client{Timeout: 10 * time.Second}
	loginBody := fmt.Sprintf(`{"email":"%s","password":"%s"}`, email, password)
	req, _ := http.NewRequest("POST", getAPIURL()+"/api/auth/login", strings.NewReader(loginBody))
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: Failed to connect to API: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		fmt.Fprintf(os.Stderr, "Error: Login failed: %s\n", string(body))
		os.Exit(1)
	}

	var loginResp struct {
		AccessToken  string `json:"accessToken"`
		RefreshToken string `json:"refreshToken"`
		ExpiresIn    int    `json:"expiresIn"`
		User         struct {
			ID      string `json:"id"`
			Email   string `json:"email"`
			IsAdmin bool   `json:"isAdmin"`
		} `json:"user"`
	}
	json.NewDecoder(resp.Body).Decode(&loginResp)

	auth := AuthConfig{
		AccessToken:  loginResp.AccessToken,
		RefreshToken: loginResp.RefreshToken,
		ExpiresAt:    time.Now().Add(time.Duration(loginResp.ExpiresIn) * time.Second),
		Email:        loginResp.User.Email,
		UserID:       loginResp.User.ID,
		IsAdmin:      loginResp.User.IsAdmin,
	}
	if err := saveAuthConfig(auth); err != nil {
		fmt.Fprintf(os.Stderr, "Error saving credentials: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Successfully logged in as %s\n", loginResp.User.Email)
	if loginResp.User.IsAdmin {
		fmt.Println("You have admin privileges for entitlement management")
	}
}

var logoutCmd = &cobra.Command{
	Use:   "logout",
	Short: "Clear stored credentials",
	Run: func(cmd *cobra.Command, args []string) {
		authPath := getAuthConfigPath()
		if err := os.Remove(authPath); err != nil && !os.IsNotExist(err) {
			fmt.Fprintf(os.Stderr, "Error removing credentials: %v\n", err)
			os.Exit(1)
		}
		fmt.Println("Logged out successfully")
	},
}

// ============================================
// LIST ENTITLEMENTS
// ============================================

var listCmd = &cobra.Command{
	Use:   "list [user-id]",
	Short: "List entitlements for a user",
	Long: `List all entitlements for a user, or your own if no user ID specified.

Examples:
  # List your own entitlements
  changes entitlement list

  # List entitlements for a specific user (admin)
  changes entitlement list user-123

  # Filter by domain
  changes entitlement list --domain getthis.money`,
	Run: runList,
}

func init() {
	listCmd.Flags().String("domain", "", "Filter by domain")
	listCmd.Flags().String("source", "", "Filter by source (subscription, purchase, free_tier, admin_grant)")
}

func runList(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	domain, _ := cmd.Flags().GetString("domain")
	source, _ := cmd.Flags().GetString("source")

	var endpoint string
	if len(args) > 0 {
		// Admin looking at another user
		endpoint = fmt.Sprintf("/api/entitlements/admin/user/%s", args[0])
	} else {
		endpoint = "/api/entitlements"
	}

	if domain != "" {
		endpoint += fmt.Sprintf("/domain/%s", domain)
	}

	resp, err := makeAuthenticatedRequest("GET", endpoint, nil, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var result struct {
		Entitlements []Entitlement `json:"entitlements"`
		Summary      struct {
			Total    int            `json:"total"`
			ByDomain map[string]int `json:"byDomain"`
			BySource map[string]int `json:"bySource"`
		} `json:"summary"`
	}
	json.Unmarshal(resp, &result)

	// Filter by source if specified
	if source != "" {
		var filtered []Entitlement
		for _, e := range result.Entitlements {
			if e.Source == source {
				filtered = append(filtered, e)
			}
		}
		result.Entitlements = filtered
	}

	// Print results
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "PRODUCT\tDOMAIN\tTIER\tSOURCE\tEXPIRES")
	fmt.Fprintln(w, "-------\t------\t----\t------\t-------")
	for _, e := range result.Entitlements {
		expires := "Never"
		if e.ExpiresAt != nil {
			expires = e.ExpiresAt.Format("2006-01-02")
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n", e.ProductName, e.Domain, e.Tier, e.Source, expires)
	}
	w.Flush()

	fmt.Printf("\nTotal: %d entitlements\n", len(result.Entitlements))
}

// ============================================
// CHECK ACCESS
// ============================================

var checkCmd = &cobra.Command{
	Use:   "check",
	Short: "Check if user has access to a feature",
	Long: `Check if a user has access to a specific feature on a domain.

Examples:
  # Check your own access
  changes entitlement check --domain getthis.money --feature payouts

  # Check another user's access (admin)
  changes entitlement check --user user-123 --domain merklemart.com --feature unlimited_listings`,
	Run: runCheck,
}

func init() {
	checkCmd.Flags().String("user", "", "User ID to check (admin only)")
	checkCmd.Flags().String("domain", "", "Domain to check (required)")
	checkCmd.Flags().String("feature", "", "Feature to check (required)")
	checkCmd.MarkFlagRequired("domain")
	checkCmd.MarkFlagRequired("feature")
}

func runCheck(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	domain, _ := cmd.Flags().GetString("domain")
	feature, _ := cmd.Flags().GetString("feature")
	userID, _ := cmd.Flags().GetString("user")

	endpoint := fmt.Sprintf("/api/entitlements/check?domain=%s&feature=%s", domain, feature)
	if userID != "" {
		endpoint = fmt.Sprintf("/api/entitlements/admin/check?userId=%s&domain=%s&feature=%s", userID, domain, feature)
	}

	resp, err := makeAuthenticatedRequest("GET", endpoint, nil, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var result struct {
		HasAccess   bool         `json:"hasAccess"`
		Entitlement *Entitlement `json:"entitlement"`
		Reason      string       `json:"reason"`
	}
	json.Unmarshal(resp, &result)

	if result.HasAccess {
		fmt.Printf("Access: GRANTED\n")
		if result.Entitlement != nil {
			fmt.Printf("Via:    %s (%s)\n", result.Entitlement.ProductName, result.Entitlement.Source)
			fmt.Printf("Tier:   %s\n", result.Entitlement.Tier)
		}
	} else {
		fmt.Printf("Access: DENIED\n")
		if result.Reason != "" {
			fmt.Printf("Reason: %s\n", result.Reason)
		}
	}
}

// ============================================
// USAGE
// ============================================

var usageCmd = &cobra.Command{
	Use:   "usage",
	Short: "View usage metrics for a user",
	Long: `View usage metrics and limits for a user.

Examples:
  # View your usage
  changes entitlement usage --domain getthis.money --metric api_calls

  # View all usage for a domain
  changes entitlement usage --domain merklemart.com`,
	Run: runUsage,
}

func init() {
	usageCmd.Flags().String("user", "", "User ID (admin only)")
	usageCmd.Flags().String("domain", "", "Domain to check (required)")
	usageCmd.Flags().String("metric", "", "Specific metric to check")
	usageCmd.MarkFlagRequired("domain")
}

func runUsage(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	domain, _ := cmd.Flags().GetString("domain")
	metric, _ := cmd.Flags().GetString("metric")

	endpoint := fmt.Sprintf("/api/entitlements/usage?domain=%s", domain)
	if metric != "" {
		endpoint += "&metric=" + metric
	}

	resp, err := makeAuthenticatedRequest("GET", endpoint, nil, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var result struct {
		Allowed    bool   `json:"allowed"`
		Current    int    `json:"current"`
		Limit      int    `json:"limit"`
		Percentage int    `json:"percentage"`
		ResetAt    string `json:"resetAt"`
	}
	json.Unmarshal(resp, &result)

	fmt.Printf("Domain:     %s\n", domain)
	if metric != "" {
		fmt.Printf("Metric:     %s\n", metric)
	}
	fmt.Printf("Usage:      %d / %d (%d%%)\n", result.Current, result.Limit, result.Percentage)
	fmt.Printf("Status:     ")
	if result.Allowed {
		fmt.Println("OK")
	} else {
		fmt.Println("LIMIT EXCEEDED")
	}
}

// ============================================
// GRANT (Admin)
// ============================================

var grantCmd = &cobra.Command{
	Use:   "grant",
	Short: "Grant an entitlement to a user (admin)",
	Long: `Grant an entitlement to a user. Requires admin privileges.

Examples:
  # Grant a product to a user
  changes entitlement grant --user user-123 --product GTM-PRO --reason "Promotional offer"

  # Grant with expiration
  changes entitlement grant --user user-123 --product MM-SELLER-PRO --expires 2025-12-31`,
	Run: runGrant,
}

func init() {
	grantCmd.Flags().String("user", "", "User ID (required)")
	grantCmd.Flags().String("product", "", "Product code (required)")
	grantCmd.Flags().String("reason", "", "Reason for grant")
	grantCmd.Flags().String("expires", "", "Expiration date (YYYY-MM-DD)")
	grantCmd.MarkFlagRequired("user")
	grantCmd.MarkFlagRequired("product")
}

func runGrant(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	userID, _ := cmd.Flags().GetString("user")
	product, _ := cmd.Flags().GetString("product")
	reason, _ := cmd.Flags().GetString("reason")
	expires, _ := cmd.Flags().GetString("expires")

	body := map[string]interface{}{
		"userId":      userID,
		"productCode": product,
	}
	if reason != "" {
		body["reason"] = reason
	}
	if expires != "" {
		body["expiresAt"] = expires + "T23:59:59Z"
	}

	bodyBytes, _ := json.Marshal(body)
	resp, err := makeAuthenticatedRequest("POST", "/api/entitlements/admin/grant", bodyBytes, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var result struct {
		Success bool   `json:"success"`
		Error   string `json:"error"`
	}
	json.Unmarshal(resp, &result)

	if result.Success {
		fmt.Printf("Successfully granted %s to user %s\n", product, userID)
	} else {
		fmt.Fprintf(os.Stderr, "Error: %s\n", result.Error)
		os.Exit(1)
	}
}

// ============================================
// REVOKE (Admin)
// ============================================

var revokeCmd = &cobra.Command{
	Use:   "revoke [grant-id]",
	Short: "Revoke an entitlement grant (admin)",
	Long: `Revoke an entitlement grant. Requires admin privileges.

Examples:
  # Revoke a grant
  changes entitlement revoke abc123-grant-id --reason "Subscription cancelled"`,
	Args: cobra.ExactArgs(1),
	Run:  runRevoke,
}

func init() {
	revokeCmd.Flags().String("reason", "", "Reason for revocation")
}

func runRevoke(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	grantID := args[0]
	reason, _ := cmd.Flags().GetString("reason")

	body := map[string]interface{}{}
	if reason != "" {
		body["reason"] = reason
	}

	bodyBytes, _ := json.Marshal(body)
	_, err := makeAuthenticatedRequest("DELETE", "/api/entitlements/admin/grant/"+grantID, bodyBytes, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Successfully revoked grant %s\n", grantID)
}

// ============================================
// APPROVERS
// ============================================

var approversCmd = &cobra.Command{
	Use:   "approvers",
	Short: "List users who can approve entitlements",
	Long: `List all users with entitlement approval privileges.

Examples:
  # List all approvers
  changes entitlement approvers

  # Filter by domain
  changes entitlement approvers --domain getthis.money`,
	Run: runApprovers,
}

func init() {
	approversCmd.Flags().String("domain", "", "Filter by domain")
}

func runApprovers(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	domain, _ := cmd.Flags().GetString("domain")

	endpoint := "/api/entitlements/admin/approvers"
	if domain != "" {
		endpoint += "?domain=" + domain
	}

	resp, err := makeAuthenticatedRequest("GET", endpoint, nil, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var result struct {
		Approvers []struct {
			ID       string   `json:"id"`
			Email    string   `json:"email"`
			Name     string   `json:"name"`
			Domains  []string `json:"domains"`
			CanGrant bool     `json:"canGrant"`
		} `json:"approvers"`
	}
	json.Unmarshal(resp, &result)

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tNAME\tEMAIL\tDOMAINS\tCAN GRANT")
	fmt.Fprintln(w, "--\t----\t-----\t-------\t---------")
	for _, a := range result.Approvers {
		domains := strings.Join(a.Domains, ", ")
		if len(domains) > 30 {
			domains = domains[:27] + "..."
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%v\n", a.ID, a.Name, a.Email, domains, a.CanGrant)
	}
	w.Flush()
}

// ============================================
// USERS
// ============================================

var usersCmd = &cobra.Command{
	Use:   "users",
	Short: "List users for a domain/application",
	Long: `List all users with entitlements for a specific domain.

Examples:
  # List users for a domain
  changes entitlement users --domain getthis.money

  # Filter by tier
  changes entitlement users --domain merklemart.com --tier pro`,
	Run: runUsers,
}

func init() {
	usersCmd.Flags().String("domain", "", "Domain to list users for (required)")
	usersCmd.Flags().String("tier", "", "Filter by tier")
	usersCmd.Flags().Bool("active", true, "Show only active entitlements")
	usersCmd.Flags().Int("limit", 50, "Maximum number of results")
	usersCmd.MarkFlagRequired("domain")
}

func runUsers(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	domain, _ := cmd.Flags().GetString("domain")
	tier, _ := cmd.Flags().GetString("tier")
	active, _ := cmd.Flags().GetBool("active")
	limit, _ := cmd.Flags().GetInt("limit")

	endpoint := fmt.Sprintf("/api/entitlements/admin/users?domain=%s&active=%v&limit=%d", domain, active, limit)
	if tier != "" {
		endpoint += "&tier=" + tier
	}

	resp, err := makeAuthenticatedRequest("GET", endpoint, nil, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var result struct {
		Users []struct {
			ID          string     `json:"id"`
			Email       string     `json:"email"`
			Name        string     `json:"name"`
			Tier        string     `json:"tier"`
			ProductCode string     `json:"productCode"`
			Source      string     `json:"source"`
			ExpiresAt   *time.Time `json:"expiresAt"`
		} `json:"users"`
		Total int `json:"total"`
	}
	json.Unmarshal(resp, &result)

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tEMAIL\tTIER\tPRODUCT\tSOURCE\tEXPIRES")
	fmt.Fprintln(w, "--\t-----\t----\t-------\t------\t-------")
	for _, u := range result.Users {
		expires := "Never"
		if u.ExpiresAt != nil {
			expires = u.ExpiresAt.Format("2006-01-02")
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\t%s\n", u.ID, u.Email, u.Tier, u.ProductCode, u.Source, expires)
	}
	w.Flush()

	fmt.Printf("\nShowing %d of %d users\n", len(result.Users), result.Total)
}

// ============================================
// AUDIT LOG
// ============================================

var logCmd = &cobra.Command{
	Use:   "log",
	Short: "View entitlement audit log",
	Long: `View audit log of entitlement changes (grants, revocations, usage).

Examples:
  # View recent log entries
  changes entitlement log

  # Filter by user
  changes entitlement log --user user-123

  # Filter by action
  changes entitlement log --action grant`,
	Run: runLog,
}

func init() {
	logCmd.Flags().String("user", "", "Filter by user ID")
	logCmd.Flags().String("domain", "", "Filter by domain")
	logCmd.Flags().String("action", "", "Filter by action (grant, revoke, usage)")
	logCmd.Flags().Int("limit", 20, "Maximum number of results")
}

func runLog(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	userID, _ := cmd.Flags().GetString("user")
	domain, _ := cmd.Flags().GetString("domain")
	action, _ := cmd.Flags().GetString("action")
	limit, _ := cmd.Flags().GetInt("limit")

	endpoint := fmt.Sprintf("/api/entitlements/admin/log?limit=%d", limit)
	if userID != "" {
		endpoint += "&userId=" + userID
	}
	if domain != "" {
		endpoint += "&domain=" + domain
	}
	if action != "" {
		endpoint += "&action=" + action
	}

	resp, err := makeAuthenticatedRequest("GET", endpoint, nil, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var result struct {
		Entries []struct {
			ID        string    `json:"id"`
			Action    string    `json:"action"`
			UserID    string    `json:"userId"`
			UserEmail string    `json:"userEmail"`
			Product   string    `json:"productCode"`
			Domain    string    `json:"domain"`
			Actor     string    `json:"actorEmail"`
			Reason    string    `json:"reason"`
			CreatedAt time.Time `json:"createdAt"`
		} `json:"entries"`
	}
	json.Unmarshal(resp, &result)

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "TIMESTAMP\tACTION\tUSER\tPRODUCT\tACTOR\tREASON")
	fmt.Fprintln(w, "---------\t------\t----\t-------\t-----\t------")
	for _, e := range result.Entries {
		reason := e.Reason
		if len(reason) > 30 {
			reason = reason[:27] + "..."
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\t%s\n",
			e.CreatedAt.Format("01-02 15:04"),
			e.Action,
			e.UserEmail,
			e.Product,
			e.Actor,
			reason)
	}
	w.Flush()
}

// ============================================
// FREEZE / UNFREEZE
// ============================================

var freezeCmd = &cobra.Command{
	Use:   "freeze [user-id]",
	Short: "Freeze all entitlements for a user (admin)",
	Long: `Freeze all entitlements for a user, preventing access to all features.

Examples:
  # Freeze a user's entitlements
  changes entitlement freeze user-123 --reason "Account review"`,
	Args: cobra.ExactArgs(1),
	Run:  runFreeze,
}

func init() {
	freezeCmd.Flags().String("reason", "", "Reason for freeze (required)")
	freezeCmd.MarkFlagRequired("reason")
}

func runFreeze(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	userID := args[0]
	reason, _ := cmd.Flags().GetString("reason")

	body := map[string]interface{}{
		"frozen": true,
		"reason": reason,
	}
	bodyBytes, _ := json.Marshal(body)

	_, err := makeAuthenticatedRequest("POST", "/api/entitlements/admin/user/"+userID+"/freeze", bodyBytes, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Entitlements frozen for user %s\n", userID)
}

var unfreezeCmd = &cobra.Command{
	Use:   "unfreeze [user-id]",
	Short: "Unfreeze entitlements for a user (admin)",
	Long: `Unfreeze entitlements for a user, restoring access.

Examples:
  # Unfreeze a user
  changes entitlement unfreeze user-123`,
	Args: cobra.ExactArgs(1),
	Run:  runUnfreeze,
}

func runUnfreeze(cmd *cobra.Command, args []string) {
	auth := mustGetAuth()
	userID := args[0]

	body := map[string]interface{}{
		"frozen": false,
	}
	bodyBytes, _ := json.Marshal(body)

	_, err := makeAuthenticatedRequest("POST", "/api/entitlements/admin/user/"+userID+"/freeze", bodyBytes, auth)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Entitlements unfrozen for user %s\n", userID)
}

// ============================================
// HELPER FUNCTIONS
// ============================================

func getAPIURL() string {
	if url := viper.GetString("entitlements_api_url"); url != "" {
		return url
	}
	if url := os.Getenv("ENTITLEMENTS_API_URL"); url != "" {
		return url
	}
	return defaultAPIURL
}

func getAuthConfigPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".adsops-utils", "entitlements-auth.json")
}

func saveAuthConfig(auth AuthConfig) error {
	path := getAuthConfigPath()
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}

	data, err := json.MarshalIndent(auth, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(path, data, 0600)
}

func loadAuthConfig() (*AuthConfig, error) {
	path := getAuthConfigPath()
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var auth AuthConfig
	if err := json.Unmarshal(data, &auth); err != nil {
		return nil, err
	}

	return &auth, nil
}

func mustGetAuth() *AuthConfig {
	// Check for API key in environment
	if apiKey := os.Getenv("ENTITLEMENTS_API_KEY"); apiKey != "" {
		return &AuthConfig{
			AccessToken: apiKey,
			IsAdmin:     true,
		}
	}

	auth, err := loadAuthConfig()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Not authenticated. Run 'changes entitlement login' first.")
		os.Exit(1)
	}

	// Check if token is expired
	if time.Now().After(auth.ExpiresAt) {
		// Try to refresh
		if auth.RefreshToken != "" {
			newAuth, err := refreshToken(auth)
			if err != nil {
				fmt.Fprintln(os.Stderr, "Session expired. Run 'changes entitlement login' again.")
				os.Exit(1)
			}
			return newAuth
		}
		fmt.Fprintln(os.Stderr, "Session expired. Run 'changes entitlement login' again.")
		os.Exit(1)
	}

	return auth
}

func refreshToken(auth *AuthConfig) (*AuthConfig, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	body := fmt.Sprintf(`{"refreshToken":"%s"}`, auth.RefreshToken)
	req, _ := http.NewRequest("POST", getAPIURL()+"/api/auth/token/refresh", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("refresh failed")
	}

	var result struct {
		AccessToken  string `json:"accessToken"`
		RefreshToken string `json:"refreshToken"`
		ExpiresIn    int    `json:"expiresIn"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	newAuth := &AuthConfig{
		AccessToken:  result.AccessToken,
		RefreshToken: result.RefreshToken,
		ExpiresAt:    time.Now().Add(time.Duration(result.ExpiresIn) * time.Second),
		Email:        auth.Email,
		UserID:       auth.UserID,
		IsAdmin:      auth.IsAdmin,
	}
	saveAuthConfig(*newAuth)

	return newAuth, nil
}

func makeAuthenticatedRequest(method, endpoint string, body []byte, auth *AuthConfig) ([]byte, error) {
	client := &http.Client{Timeout: 30 * time.Second}

	var req *http.Request
	var err error
	if body != nil {
		req, err = http.NewRequest(method, getAPIURL()+endpoint, strings.NewReader(string(body)))
	} else {
		req, err = http.NewRequest(method, getAPIURL()+endpoint, nil)
	}
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Bearer "+auth.AccessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %v", err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	if resp.StatusCode == 401 {
		return nil, fmt.Errorf("unauthorized - please login again")
	}
	if resp.StatusCode == 403 {
		return nil, fmt.Errorf("forbidden - insufficient privileges")
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("API error (%d): %s", resp.StatusCode, string(respBody))
	}

	return respBody, nil
}
