package ghmigrate

import (
	"github.com/spf13/cobra"
)

// GHMigrateCmd represents the gh-migrate command group
var GHMigrateCmd = &cobra.Command{
	Use:     "gh-migrate",
	Aliases: []string{"ghm", "github-migrate"},
	Short:   "Migrate GitHub Issues to Changes ticketing system",
	Long: `Migrate GitHub Issues to the After Dark Systems Changes ticketing system.

This tool fetches issues from GitHub repositories and converts them into
Changes tickets, preserving metadata, labels, and comments.

Examples:
  # List issues from a repository
  gh-migrate --list --repos owner/repo

  # List issues from multiple repos
  gh-migrate -l -r owner/repo1,owner/repo2

  # Import issues from a repository
  gh-migrate --import --repos owner/repo

  # Import only open issues
  gh-migrate -i -r owner/repo --status open

  # Check migration status
  gh-migrate --status

  # Use custom GitHub Enterprise URL
  gh-migrate -l -r owner/repo -g https://github.mycompany.com/api/v3`,
}

func init() {
	// Global flags for gh-migrate
	GHMigrateCmd.PersistentFlags().StringP("user", "u", "", "GitHub username (or set GITHUB_USER env var)")
	GHMigrateCmd.PersistentFlags().StringP("api-key", "a", "", "GitHub personal access token (or set GITHUB_TOKEN env var)")
	GHMigrateCmd.PersistentFlags().StringP("gh-url", "g", "https://api.github.com", "GitHub API URL (for GitHub Enterprise)")
	GHMigrateCmd.PersistentFlags().StringSliceP("repos", "r", []string{}, "Repository list (owner/repo format, comma-separated)")

	// Action flags
	GHMigrateCmd.Flags().BoolP("list", "l", false, "List GitHub issues from specified repos")
	GHMigrateCmd.Flags().BoolP("import", "i", false, "Import GitHub issues to Changes system")
	GHMigrateCmd.Flags().BoolP("status", "s", false, "Show migration status")

	// Filter flags
	GHMigrateCmd.Flags().String("issue-status", "all", "Filter by issue status (open, closed, all)")
	GHMigrateCmd.Flags().StringSlice("labels", []string{}, "Filter by labels")
	GHMigrateCmd.Flags().Int("limit", 100, "Maximum number of issues to fetch per repo")

	// Import options
	GHMigrateCmd.Flags().Bool("dry-run", false, "Show what would be imported without importing")
	GHMigrateCmd.Flags().Bool("include-comments", true, "Include issue comments in migration")
	GHMigrateCmd.Flags().Bool("include-closed", false, "Include closed issues in migration")
	GHMigrateCmd.Flags().String("default-priority", "normal", "Default priority for imported tickets")
	GHMigrateCmd.Flags().String("default-industry", "", "Default industry for imported tickets")

	// Set command run function
	GHMigrateCmd.Run = runGHMigrate
}
