package ticket

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/spf13/cobra"
)

// LocalTicket represents a ticket stored in local JSON files
type LocalTicket struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Description string    `json:"description"`
	Status      string    `json:"status"`
	Priority    string    `json:"priority"`
	Risk        string    `json:"risk"`
	Type        string    `json:"type"`
	Industry    string    `json:"industry"`
	CreatedBy   string    `json:"created_by"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
	Assignee    string    `json:"assignee"`
	Sprint      string    `json:"sprint"`
}

var listCmd = &cobra.Command{
	Use:     "list",
	Aliases: []string{"ls"},
	Short:   "List change tickets",
	Long: `List change tickets with optional filters.

Examples:
  # List all tickets
  changes ticket list

  # List only pending tickets
  changes ticket list --status submitted,in_review

  # List high priority tickets
  changes ticket list --priority high,urgent,emergency

  # List tickets assigned to you
  changes ticket list --mine

  # List tickets with JSON output
  changes ticket list --output json`,
	Run: runList,
}

func init() {
	listCmd.Flags().StringSlice("status", []string{}, "Filter by status")
	listCmd.Flags().StringSlice("priority", []string{}, "Filter by priority")
	listCmd.Flags().StringSlice("risk", []string{}, "Filter by risk level")
	listCmd.Flags().Bool("mine", false, "Show only tickets created by me")
	listCmd.Flags().Bool("assigned", false, "Show only tickets assigned to me")
	listCmd.Flags().Int("limit", 50, "Maximum number of tickets to display")
	listCmd.Flags().String("sort", "created_at", "Sort field (created_at, updated_at, priority)")
	listCmd.Flags().Bool("desc", true, "Sort descending")
}

// getTicketsDir returns the path to the tickets directory
func getTicketsDir() string {
	// First try current directory
	if _, err := os.Stat("tickets"); err == nil {
		return "tickets"
	}
	// Try relative to executable
	exe, err := os.Executable()
	if err == nil {
		dir := filepath.Dir(exe)
		ticketsDir := filepath.Join(dir, "tickets")
		if _, err := os.Stat(ticketsDir); err == nil {
			return ticketsDir
		}
	}
	// Default
	return "tickets"
}

// loadLocalTickets loads tickets from the local tickets directory
func loadLocalTickets() ([]LocalTicket, error) {
	ticketsDir := getTicketsDir()

	entries, err := os.ReadDir(ticketsDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read tickets directory: %w", err)
	}

	var tickets []LocalTicket
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(ticketsDir, entry.Name()))
		if err != nil {
			continue
		}

		var ticket LocalTicket
		if err := json.Unmarshal(data, &ticket); err != nil {
			continue
		}

		tickets = append(tickets, ticket)
	}

	return tickets, nil
}

func runList(cmd *cobra.Command, args []string) {
	statusFilter, _ := cmd.Flags().GetStringSlice("status")
	priorityFilter, _ := cmd.Flags().GetStringSlice("priority")
	limit, _ := cmd.Flags().GetInt("limit")
	sortField, _ := cmd.Flags().GetString("sort")
	descending, _ := cmd.Flags().GetBool("desc")

	tickets, err := loadLocalTickets()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading tickets: %v\n", err)
		os.Exit(1)
	}

	// Apply filters
	var filtered []LocalTicket
	for _, t := range tickets {
		// Status filter
		if len(statusFilter) > 0 {
			match := false
			for _, s := range statusFilter {
				if strings.EqualFold(t.Status, s) {
					match = true
					break
				}
			}
			if !match {
				continue
			}
		}

		// Priority filter
		if len(priorityFilter) > 0 {
			match := false
			for _, p := range priorityFilter {
				if strings.EqualFold(t.Priority, p) {
					match = true
					break
				}
			}
			if !match {
				continue
			}
		}

		filtered = append(filtered, t)
	}

	// Sort
	sort.Slice(filtered, func(i, j int) bool {
		var less bool
		switch sortField {
		case "priority":
			priorityOrder := map[string]int{"emergency": 0, "urgent": 1, "high": 2, "normal": 3, "low": 4}
			less = priorityOrder[strings.ToLower(filtered[i].Priority)] < priorityOrder[strings.ToLower(filtered[j].Priority)]
		case "updated_at":
			less = filtered[i].UpdatedAt.Before(filtered[j].UpdatedAt)
		default: // created_at
			less = filtered[i].CreatedAt.Before(filtered[j].CreatedAt)
		}
		if descending {
			return !less
		}
		return less
	})

	// Apply limit
	if limit > 0 && len(filtered) > limit {
		filtered = filtered[:limit]
	}

	// Output
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "TICKET\tSTATUS\tPRIORITY\tTITLE\tCREATED")
	fmt.Fprintln(w, "------\t------\t--------\t-----\t-------")

	for _, t := range filtered {
		title := t.Title
		if len(title) > 40 {
			title = title[:37] + "..."
		}
		created := t.CreatedAt.Format("2006-01-02")
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n", t.ID, t.Status, t.Priority, title, created)
	}
	w.Flush()

	if len(filtered) == 0 {
		fmt.Println("\nNo tickets found.")
	} else {
		fmt.Printf("\n%d ticket(s) found.\n", len(filtered))
	}
}
