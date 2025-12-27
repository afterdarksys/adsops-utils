package commands

import (
	"fmt"
	"os"

	"github.com/afterdarksys/adsops-utils/internal/cli/commands/approval"
	"github.com/afterdarksys/adsops-utils/internal/cli/commands/auth"
	"github.com/afterdarksys/adsops-utils/internal/cli/commands/config"
	"github.com/afterdarksys/adsops-utils/internal/cli/commands/employee"
	"github.com/afterdarksys/adsops-utils/internal/cli/commands/group"
	"github.com/afterdarksys/adsops-utils/internal/cli/commands/ticket"
	"github.com/afterdarksys/adsops-utils/internal/cli/commands/user"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	cfgFile string
	rootCmd = &cobra.Command{
		Use:   "changes",
		Short: "After Dark Systems Change Management CLI",
		Long: `A CLI tool for managing change tickets in the After Dark Systems
Change Management platform.

This tool allows you to:
  - Create, view, edit, and manage change tickets
  - Approve or deny change requests
  - Track compliance and audit trails
  - Integrate with your CI/CD pipelines`,
	}
)

// Execute runs the root command
func Execute() error {
	return rootCmd.Execute()
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.adsops-utils/config.yaml)")
	rootCmd.PersistentFlags().String("api-url", "https://api.changes.afterdarksys.com", "API server URL")
	rootCmd.PersistentFlags().Bool("verbose", false, "Enable verbose output")
	rootCmd.PersistentFlags().String("output", "table", "Output format (table, json, yaml)")

	// Bind flags to viper
	viper.BindPFlag("api_url", rootCmd.PersistentFlags().Lookup("api-url"))
	viper.BindPFlag("verbose", rootCmd.PersistentFlags().Lookup("verbose"))
	viper.BindPFlag("output", rootCmd.PersistentFlags().Lookup("output"))

	// Add subcommands
	rootCmd.AddCommand(ticket.TicketCmd)
	rootCmd.AddCommand(approval.ApprovalCmd)
	rootCmd.AddCommand(auth.AuthCmd)
	rootCmd.AddCommand(config.ConfigCmd)
	rootCmd.AddCommand(user.UserCmd)
	rootCmd.AddCommand(employee.EmployeeCmd)
	rootCmd.AddCommand(group.GroupCmd)
}

func initConfig() {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			fmt.Fprintln(os.Stderr, "Error finding home directory:", err)
			os.Exit(1)
		}

		configDir := home + "/.adsops-utils"

		// Create config directory if it doesn't exist
		if err := os.MkdirAll(configDir, 0700); err != nil {
			fmt.Fprintln(os.Stderr, "Error creating config directory:", err)
			os.Exit(1)
		}

		viper.AddConfigPath(configDir)
		viper.SetConfigType("yaml")
		viper.SetConfigName("config")
	}

	viper.SetEnvPrefix("ADSOPS")
	viper.AutomaticEnv()

	if err := viper.ReadInConfig(); err == nil {
		if viper.GetBool("verbose") {
			fmt.Fprintln(os.Stderr, "Using config file:", viper.ConfigFileUsed())
		}
	}
}
