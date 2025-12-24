package user

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"text/tabwriter"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var sshAccessCmd = &cobra.Command{
	Use:   "ssh-access",
	Short: "Manage SSH proxy access permissions",
	Long: `Manage SSH proxy access for users.

SSH proxy access allows users to connect to backend servers through the
AfterDark SSH Gateway (sshgw.afterdarksys.com).

Examples:
  # Grant access
  changes user ssh-access grant user@example.com

  # Revoke access
  changes user ssh-access revoke user@example.com

  # List all users with access
  changes user ssh-access list

  # Check status for a specific user
  changes user ssh-access status user@example.com`,
}

func init() {
	sshAccessCmd.AddCommand(sshGrantCmd)
	sshAccessCmd.AddCommand(sshRevokeCmd)
	sshAccessCmd.AddCommand(sshListCmd)
	sshAccessCmd.AddCommand(sshStatusCmd)
}

// API client helper
func getAPIClient() (*http.Client, string, error) {
	baseURL := viper.GetString("login_api_url")
	if baseURL == "" {
		baseURL = "https://login.afterdarksys.com"
	}

	token := viper.GetString("auth_token")
	if token == "" {
		// Try to read from file
		tokenFile := os.ExpandEnv("$HOME/.config/afterdark/token")
		data, err := os.ReadFile(tokenFile)
		if err != nil {
			return nil, "", fmt.Errorf("not authenticated. Run 'changes auth login' first")
		}
		token = strings.TrimSpace(string(data))
	}

	return &http.Client{}, baseURL, nil
}

func makeAPIRequest(method, endpoint string, body interface{}) (*http.Response, error) {
	client, baseURL, err := getAPIClient()
	if err != nil {
		return nil, err
	}

	token := viper.GetString("auth_token")
	if token == "" {
		tokenFile := os.ExpandEnv("$HOME/.config/afterdark/token")
		data, _ := os.ReadFile(tokenFile)
		token = strings.TrimSpace(string(data))
	}

	var reqBody io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		reqBody = bytes.NewBuffer(jsonBody)
	}

	req, err := http.NewRequest(method, baseURL+endpoint, reqBody)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")

	return client.Do(req)
}

// Grant SSH proxy access
var sshGrantCmd = &cobra.Command{
	Use:   "grant [email]",
	Short: "Grant SSH proxy access to a user",
	Long: `Grant SSH proxy access to a user by email.

This allows the user to:
- Connect to backend servers via the SSH gateway
- Manage their SSH keys via the web portal
- View their active sessions

Examples:
  changes user ssh-access grant user@example.com`,
	Args: cobra.ExactArgs(1),
	Run:  runSSHGrant,
}

func runSSHGrant(cmd *cobra.Command, args []string) {
	email := args[0]

	fmt.Printf("Granting SSH proxy access to %s...\n", email)

	resp, err := makeAPIRequest("POST", "/api/admin/ssh-proxy-access", map[string]string{
		"email": email,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing response: %v\n", err)
		os.Exit(1)
	}

	if resp.StatusCode != 200 {
		errMsg := result["error"]
		if errMsg == nil {
			errMsg = "Unknown error"
		}
		fmt.Fprintf(os.Stderr, "Error: %v\n", errMsg)
		os.Exit(1)
	}

	fmt.Printf("SSH proxy access granted to %s\n", email)
}

// Revoke SSH proxy access
var sshRevokeCmd = &cobra.Command{
	Use:   "revoke [email]",
	Short: "Revoke SSH proxy access from a user",
	Long: `Revoke SSH proxy access from a user by email.

This will:
- Remove access to the SSH gateway
- Terminate any active SSH sessions
- Remove the Security Settings from their dashboard

Examples:
  changes user ssh-access revoke user@example.com`,
	Args: cobra.ExactArgs(1),
	Run:  runSSHRevoke,
}

func runSSHRevoke(cmd *cobra.Command, args []string) {
	email := args[0]

	fmt.Printf("Revoking SSH proxy access from %s...\n", email)

	resp, err := makeAPIRequest("DELETE", "/api/admin/ssh-proxy-access/"+email, nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing response: %v\n", err)
		os.Exit(1)
	}

	if resp.StatusCode != 200 {
		errMsg := result["error"]
		if errMsg == nil {
			errMsg = "Unknown error"
		}
		fmt.Fprintf(os.Stderr, "Error: %v\n", errMsg)
		os.Exit(1)
	}

	fmt.Printf("SSH proxy access revoked from %s\n", email)
}

// List users with SSH proxy access
var sshListCmd = &cobra.Command{
	Use:   "list",
	Short: "List users with SSH proxy access",
	Long: `List all users who have SSH proxy access.

Displays:
- Email address
- Role (admin/user)
- Access type (admin privilege or explicit grant)
- When access was granted

Examples:
  changes user ssh-access list`,
	Run: runSSHList,
}

func runSSHList(cmd *cobra.Command, args []string) {
	resp, err := makeAPIRequest("GET", "/api/admin/ssh-proxy-access", nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	var result struct {
		Success bool `json:"success"`
		Users   []struct {
			ID             string `json:"id"`
			Email          string `json:"email"`
			Role           string `json:"role"`
			SSHProxyAccess bool   `json:"ssh_proxy_access"`
			IsAdmin        bool   `json:"is_admin"`
			UpdatedAt      string `json:"updated_at"`
			UpdatedBy      string `json:"updated_by"`
		} `json:"users"`
		Error string `json:"error"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing response: %v\n", err)
		os.Exit(1)
	}

	if resp.StatusCode != 200 {
		fmt.Fprintf(os.Stderr, "Error: %s\n", result.Error)
		os.Exit(1)
	}

	if len(result.Users) == 0 {
		fmt.Println("No users with SSH proxy access found.")
		return
	}

	fmt.Println("Users with SSH Proxy Access")
	fmt.Println("===========================")
	fmt.Println()

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "EMAIL\tROLE\tACCESS TYPE\tGRANTED")

	for _, user := range result.Users {
		accessType := "Explicit Grant"
		if user.IsAdmin {
			accessType = "Admin Privilege"
		}

		grantedAt := user.UpdatedAt
		if grantedAt == "" {
			grantedAt = "-"
		}

		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n",
			user.Email,
			user.Role,
			accessType,
			grantedAt,
		)
	}
	w.Flush()

	fmt.Printf("\nTotal: %d user(s)\n", len(result.Users))
}

// Check SSH proxy access status for a user
var sshStatusCmd = &cobra.Command{
	Use:   "status [email]",
	Short: "Check SSH proxy access status for a user",
	Long: `Check if a user has SSH proxy access.

Examples:
  changes user ssh-access status user@example.com`,
	Args: cobra.ExactArgs(1),
	Run:  runSSHStatus,
}

func runSSHStatus(cmd *cobra.Command, args []string) {
	email := args[0]

	resp, err := makeAPIRequest("GET", "/api/admin/ssh-proxy-access/"+email, nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	var result struct {
		Success        bool   `json:"success"`
		Email          string `json:"email"`
		SSHProxyAccess bool   `json:"ssh_proxy_access"`
		Error          string `json:"error"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing response: %v\n", err)
		os.Exit(1)
	}

	if resp.StatusCode == 404 {
		fmt.Fprintf(os.Stderr, "User not found: %s\n", email)
		os.Exit(1)
	}

	if resp.StatusCode != 200 {
		fmt.Fprintf(os.Stderr, "Error: %s\n", result.Error)
		os.Exit(1)
	}

	fmt.Printf("SSH Proxy Access Status for %s\n", email)
	fmt.Println(strings.Repeat("=", 40+len(email)))
	fmt.Println()

	if result.SSHProxyAccess {
		fmt.Println("Status: ENABLED")
		fmt.Println()
		fmt.Println("This user can:")
		fmt.Println("  - Connect to backend servers via SSH gateway")
		fmt.Println("  - Manage SSH keys in their account settings")
		fmt.Println("  - View and terminate active sessions")
	} else {
		fmt.Println("Status: DISABLED")
		fmt.Println()
		fmt.Println("To grant access, run:")
		fmt.Printf("  changes user ssh-access grant %s\n", email)
	}
}
