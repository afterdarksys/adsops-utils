package ghmigrate

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

// MigrationState tracks which issues have been migrated
type MigrationState struct {
	Migrations []MigrationRecord `json:"migrations"`
	UpdatedAt  time.Time         `json:"updated_at"`
}

// MigrationRecord tracks a single migrated issue
type MigrationRecord struct {
	GitHubRepo    string    `json:"github_repo"`
	GitHubIssue   int       `json:"github_issue"`
	GitHubURL     string    `json:"github_url"`
	ChangesTicket string    `json:"changes_ticket"`
	MigratedAt    time.Time `json:"migrated_at"`
	MigratedBy    string    `json:"migrated_by"`
}

// TicketData matches the Changes system ticket format
type TicketData struct {
	ID                   string           `json:"id"`
	Title                string           `json:"title"`
	Description          string           `json:"description"`
	Status               string           `json:"status"`
	Priority             string           `json:"priority"`
	Risk                 string           `json:"risk"`
	Type                 string           `json:"type"`
	Industry             string           `json:"industry"`
	ComplianceFrameworks []string         `json:"compliance_frameworks"`
	AffectedSystems      []string         `json:"affected_systems"`
	AcceptanceCriteria   []string         `json:"acceptance_criteria"`
	TestingPlan          string           `json:"testing_plan"`
	RollbackPlan         string           `json:"rollback_plan"`
	CreatedBy            string           `json:"created_by"`
	CreatedAt            string           `json:"created_at"`
	UpdatedAt            string           `json:"updated_at"`
	Sprint               string           `json:"sprint"`
	Assignee             *string          `json:"assignee"`
	ApprovalsRequired    []string         `json:"approvals_required"`
	Approvals            []string         `json:"approvals"`
	Dependencies         []string         `json:"dependencies"`
	Comments             []TicketComment  `json:"comments"`
	ExternalReferences   []ExternalRef    `json:"external_references"`
}

// TicketComment represents a comment on a ticket
type TicketComment struct {
	Author    string `json:"author"`
	Timestamp string `json:"timestamp"`
	Text      string `json:"text"`
}

// ExternalRef stores reference to the original GitHub issue
type ExternalRef struct {
	System string `json:"system"`
	ID     string `json:"id"`
	URL    string `json:"url"`
}

func runGHMigrate(cmd *cobra.Command, args []string) {
	// Get action flags
	listFlag, _ := cmd.Flags().GetBool("list")
	importFlag, _ := cmd.Flags().GetBool("import")
	statusFlag, _ := cmd.Flags().GetBool("status")

	// Validate at least one action is specified
	if !listFlag && !importFlag && !statusFlag {
		fmt.Println("Error: must specify an action flag (-l/--list, -i/--import, or -s/--status)")
		fmt.Println()
		cmd.Help()
		os.Exit(1)
	}

	// Handle status first (doesn't need repos)
	if statusFlag {
		runStatus(cmd)
		return
	}

	// Get repos
	repos, _ := cmd.Flags().GetStringSlice("repos")
	if len(repos) == 0 {
		fmt.Println("Error: --repos/-r is required for list and import operations")
		fmt.Println("Example: gh-migrate -l -r owner/repo")
		os.Exit(1)
	}

	// Get GitHub credentials
	token := getGitHubToken(cmd)
	username := getGitHubUsername(cmd)
	ghURL, _ := cmd.Flags().GetString("gh-url")

	// Create GitHub client
	client := NewGitHubClient(ghURL, token, username)

	if listFlag {
		runList(cmd, client, repos)
	} else if importFlag {
		runImport(cmd, client, repos)
	}
}

func getGitHubToken(cmd *cobra.Command) string {
	token, _ := cmd.Flags().GetString("api-key")
	if token == "" {
		token = viper.GetString("github.token")
	}
	if token == "" {
		token = os.Getenv("GITHUB_TOKEN")
	}
	if token == "" {
		token = os.Getenv("GH_TOKEN")
	}
	return token
}

func getGitHubUsername(cmd *cobra.Command) string {
	user, _ := cmd.Flags().GetString("user")
	if user == "" {
		user = viper.GetString("github.user")
	}
	if user == "" {
		user = os.Getenv("GITHUB_USER")
	}
	return user
}

func runList(cmd *cobra.Command, client *GitHubClient, repos []string) {
	state, _ := cmd.Flags().GetString("issue-status")
	labels, _ := cmd.Flags().GetStringSlice("labels")
	limit, _ := cmd.Flags().GetInt("limit")

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "REPO\tISSUE\tSTATE\tTITLE\tCREATED\tLABELS")
	fmt.Fprintln(w, "----\t-----\t-----\t-----\t-------\t------")

	totalIssues := 0
	for _, repoStr := range repos {
		owner, repo, err := ParseRepoString(repoStr)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: %v\n", err)
			continue
		}

		issues, err := client.ListIssues(owner, repo, state, labels, limit)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error fetching issues from %s: %v\n", repoStr, err)
			continue
		}

		for _, issue := range issues {
			title := issue.Title
			if len(title) > 50 {
				title = title[:47] + "..."
			}

			labelNames := make([]string, len(issue.Labels))
			for i, l := range issue.Labels {
				labelNames[i] = l.Name
			}
			labelsStr := strings.Join(labelNames, ",")
			if len(labelsStr) > 30 {
				labelsStr = labelsStr[:27] + "..."
			}

			fmt.Fprintf(w, "%s\t#%d\t%s\t%s\t%s\t%s\n",
				repoStr,
				issue.Number,
				issue.State,
				title,
				issue.CreatedAt.Format("2006-01-02"),
				labelsStr,
			)
			totalIssues++
		}
	}
	w.Flush()

	fmt.Printf("\n%d issue(s) found.\n", totalIssues)
}

func runImport(cmd *cobra.Command, client *GitHubClient, repos []string) {
	state, _ := cmd.Flags().GetString("issue-status")
	labels, _ := cmd.Flags().GetStringSlice("labels")
	limit, _ := cmd.Flags().GetInt("limit")
	dryRun, _ := cmd.Flags().GetBool("dry-run")
	includeComments, _ := cmd.Flags().GetBool("include-comments")
	includeClosed, _ := cmd.Flags().GetBool("include-closed")
	defaultPriority, _ := cmd.Flags().GetString("default-priority")
	defaultIndustry, _ := cmd.Flags().GetString("default-industry")

	// If not including closed, force state to open
	if !includeClosed && state == "all" {
		state = "open"
	}

	// Load migration state
	migrationState := loadMigrationState()

	if dryRun {
		fmt.Println("DRY RUN - no changes will be made")
		fmt.Println()
	}

	var imported, skipped, failed int

	for _, repoStr := range repos {
		owner, repo, err := ParseRepoString(repoStr)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: %v\n", err)
			continue
		}

		fmt.Printf("Processing repository: %s\n", repoStr)

		issues, err := client.ListIssues(owner, repo, state, labels, limit)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error fetching issues from %s: %v\n", repoStr, err)
			failed++
			continue
		}

		for _, issue := range issues {
			fmt.Printf("  Issue #%d: %s... ", issue.Number, truncate(issue.Title, 40))

			// Check if already migrated
			if isAlreadyMigrated(migrationState, repoStr, issue.Number) {
				fmt.Println("SKIPPED (already migrated)")
				skipped++
				continue
			}

			// Get comments if requested
			var comments []GitHubComment
			if includeComments && issue.Comments > 0 {
				comments, err = client.GetIssueComments(owner, repo, issue.Number)
				if err != nil {
					fmt.Printf("Warning: failed to fetch comments: %v\n", err)
				}
			}

			// Convert to ticket
			ticket, err := convertIssueToTicket(issue, comments, repoStr, defaultPriority, defaultIndustry)
			if err != nil {
				fmt.Printf("FAILED (conversion error: %v)\n", err)
				failed++
				continue
			}

			if dryRun {
				fmt.Printf("would import as %s\n", ticket.ID)
				imported++
				continue
			}

			// Save ticket
			if err := saveTicket(ticket); err != nil {
				fmt.Printf("FAILED (save error: %v)\n", err)
				failed++
				continue
			}

			// Record migration
			record := MigrationRecord{
				GitHubRepo:    repoStr,
				GitHubIssue:   issue.Number,
				GitHubURL:     issue.HTMLURL,
				ChangesTicket: ticket.ID,
				MigratedAt:    time.Now().UTC(),
				MigratedBy:    getCurrentUser(),
			}
			migrationState.Migrations = append(migrationState.Migrations, record)

			fmt.Printf("IMPORTED as %s\n", ticket.ID)
			imported++
		}
	}

	// Save migration state
	if !dryRun {
		migrationState.UpdatedAt = time.Now().UTC()
		saveMigrationState(migrationState)
	}

	fmt.Println()
	fmt.Printf("Import complete: %d imported, %d skipped, %d failed\n", imported, skipped, failed)
}

func runStatus(cmd *cobra.Command) {
	state := loadMigrationState()

	if len(state.Migrations) == 0 {
		fmt.Println("No migrations recorded yet.")
		return
	}

	fmt.Printf("Migration Status (last updated: %s)\n", state.UpdatedAt.Format(time.RFC3339))
	fmt.Println()

	// Group by repo
	byRepo := make(map[string][]MigrationRecord)
	for _, m := range state.Migrations {
		byRepo[m.GitHubRepo] = append(byRepo[m.GitHubRepo], m)
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "REPO\tGH ISSUE\tCHANGES TICKET\tMIGRATED AT")
	fmt.Fprintln(w, "----\t--------\t--------------\t-----------")

	for repo, records := range byRepo {
		for _, r := range records {
			fmt.Fprintf(w, "%s\t#%d\t%s\t%s\n",
				repo,
				r.GitHubIssue,
				r.ChangesTicket,
				r.MigratedAt.Format("2006-01-02 15:04"),
			)
		}
	}
	w.Flush()

	fmt.Printf("\nTotal: %d issues migrated from %d repositories\n", len(state.Migrations), len(byRepo))
}

func convertIssueToTicket(issue GitHubIssue, comments []GitHubComment, repo, defaultPriority, defaultIndustry string) (*TicketData, error) {
	ticketID, err := getNextTicketNumber()
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()

	// Determine priority from labels
	priority := defaultPriority
	for _, label := range issue.Labels {
		name := strings.ToLower(label.Name)
		switch {
		case strings.Contains(name, "critical") || strings.Contains(name, "emergency"):
			priority = "emergency"
		case strings.Contains(name, "urgent") || strings.Contains(name, "p0"):
			priority = "urgent"
		case strings.Contains(name, "high") || strings.Contains(name, "p1"):
			priority = "high"
		case strings.Contains(name, "low") || strings.Contains(name, "p3"):
			priority = "low"
		}
	}

	// Determine risk from labels
	risk := "medium"
	for _, label := range issue.Labels {
		name := strings.ToLower(label.Name)
		if strings.Contains(name, "risk:high") || strings.Contains(name, "security") {
			risk = "high"
		} else if strings.Contains(name, "risk:low") || strings.Contains(name, "minor") {
			risk = "low"
		}
	}

	// Determine ticket type from labels
	ticketType := "standard"
	for _, label := range issue.Labels {
		name := strings.ToLower(label.Name)
		switch {
		case strings.Contains(name, "bug") || strings.Contains(name, "fix"):
			ticketType = "bug_fix"
		case strings.Contains(name, "feature") || strings.Contains(name, "enhancement"):
			ticketType = "feature"
		case strings.Contains(name, "security"):
			ticketType = "security"
		case strings.Contains(name, "maintenance"):
			ticketType = "maintenance"
		}
	}

	// Map status
	status := "draft"
	if issue.State == "closed" {
		status = "closed"
	}

	// Extract label names for affected systems
	labelNames := make([]string, len(issue.Labels))
	for i, l := range issue.Labels {
		labelNames[i] = l.Name
	}

	// Build description with GitHub reference
	description := issue.Body
	if description == "" {
		description = "(No description provided)"
	}
	description = fmt.Sprintf("%s\n\n---\n_Migrated from GitHub: %s_", description, issue.HTMLURL)

	// Convert comments
	var ticketComments []TicketComment
	// Add original issue as first comment
	ticketComments = append(ticketComments, TicketComment{
		Author:    fmt.Sprintf("%s@github.com", issue.User.Login),
		Timestamp: issue.CreatedAt.Format(time.RFC3339),
		Text:      fmt.Sprintf("Original issue created by @%s on GitHub", issue.User.Login),
	})

	for _, c := range comments {
		ticketComments = append(ticketComments, TicketComment{
			Author:    fmt.Sprintf("%s@github.com", c.User.Login),
			Timestamp: c.CreatedAt.Format(time.RFC3339),
			Text:      c.Body,
		})
	}

	// Calculate sprint
	_, week := now.ISOWeek()
	quarter := (now.Month()-1)/3 + 1
	sprint := fmt.Sprintf("%d-Q%d-Sprint-%d", now.Year(), quarter, (week-1)%2+1)

	// Set assignee if present
	var assignee *string
	if issue.Assignee != nil {
		assigneeEmail := fmt.Sprintf("%s@github.com", issue.Assignee.Login)
		assignee = &assigneeEmail
	}

	ticket := &TicketData{
		ID:                   ticketID,
		Title:                fmt.Sprintf("[GH#%d] %s", issue.Number, issue.Title),
		Description:          description,
		Status:               status,
		Priority:             priority,
		Risk:                 risk,
		Type:                 ticketType,
		Industry:             defaultIndustry,
		ComplianceFrameworks: []string{},
		AffectedSystems:      labelNames,
		AcceptanceCriteria:   []string{},
		TestingPlan:          "",
		RollbackPlan:         "",
		CreatedBy:            fmt.Sprintf("%s@github.com", issue.User.Login),
		CreatedAt:            issue.CreatedAt.Format(time.RFC3339),
		UpdatedAt:            now.Format(time.RFC3339),
		Sprint:               sprint,
		Assignee:             assignee,
		ApprovalsRequired:    []string{},
		Approvals:            []string{},
		Dependencies:         []string{},
		Comments:             ticketComments,
		ExternalReferences: []ExternalRef{
			{
				System: "github",
				ID:     fmt.Sprintf("%s#%d", repo, issue.Number),
				URL:    issue.HTMLURL,
			},
		},
	}

	return ticket, nil
}

// Helper functions

func getTicketsDir() string {
	if _, err := os.Stat("tickets"); err == nil {
		return "tickets"
	}
	return "tickets"
}

func getMigrationStateFile() string {
	ticketsDir := getTicketsDir()
	return filepath.Join(ticketsDir, ".gh-migration-state.json")
}

func loadMigrationState() *MigrationState {
	state := &MigrationState{
		Migrations: []MigrationRecord{},
	}

	data, err := os.ReadFile(getMigrationStateFile())
	if err != nil {
		return state
	}

	json.Unmarshal(data, state)
	return state
}

func saveMigrationState(state *MigrationState) error {
	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(getMigrationStateFile(), data, 0600)
}

func isAlreadyMigrated(state *MigrationState, repo string, issueNumber int) bool {
	for _, m := range state.Migrations {
		if m.GitHubRepo == repo && m.GitHubIssue == issueNumber {
			return true
		}
	}
	return false
}

func getNextTicketNumber() (string, error) {
	ticketsDir := getTicketsDir()
	year := time.Now().Year()

	if err := os.MkdirAll(ticketsDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create tickets directory: %w", err)
	}

	// Scan for existing tickets
	entries, err := os.ReadDir(ticketsDir)
	if err != nil {
		return "", err
	}

	var maxNum int
	prefix := fmt.Sprintf("CHG-%d-", year)
	for _, entry := range entries {
		name := entry.Name()
		if !strings.HasPrefix(name, prefix) || !strings.HasSuffix(name, ".json") {
			continue
		}
		numStr := strings.TrimPrefix(name, prefix)
		numStr = strings.TrimSuffix(numStr, ".json")
		var num int
		fmt.Sscanf(numStr, "%d", &num)
		if num > maxNum {
			maxNum = num
		}
	}

	nextNum := maxNum + 1
	ticketID := fmt.Sprintf("CHG-%d-%05d", year, nextNum)

	return ticketID, nil
}

func saveTicket(ticket *TicketData) error {
	ticketsDir := getTicketsDir()
	if err := os.MkdirAll(ticketsDir, 0755); err != nil {
		return err
	}

	filename := filepath.Join(ticketsDir, ticket.ID+".json")
	data, err := json.MarshalIndent(ticket, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filename, data, 0600)
}

func getCurrentUser() string {
	user := os.Getenv("USER")
	if user == "" {
		user = "unknown"
	}
	return user + "@afterdarksys.com"
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}
