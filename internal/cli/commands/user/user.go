package user

import (
	"github.com/spf13/cobra"
)

// UserCmd represents the user command group
var UserCmd = &cobra.Command{
	Use:   "user",
	Short: "User management commands",
	Long: `Manage user accounts and permissions.

Examples:
  # Grant SSH proxy access to a user
  changes user ssh-access grant user@example.com

  # Revoke SSH proxy access from a user
  changes user ssh-access revoke user@example.com

  # List users with SSH proxy access
  changes user ssh-access list

  # Check SSH proxy access status for a user
  changes user ssh-access status user@example.com`,
}

func init() {
	UserCmd.AddCommand(sshAccessCmd)
}
