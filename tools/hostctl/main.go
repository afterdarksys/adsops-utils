package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spf13/cobra"
)

var (
	// Global flags
	jsonOutput bool
	verbose    bool

	// Version information
	version = "1.0.0"
	buildDate = "2024-01-13"
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "hostctl",
		Short: "Host management CLI for inventory database",
		Long:  `A comprehensive CLI tool to manage hosts in the inventory database with support for CRUD operations, status management, and advanced querying.`,
		Version: version,
	}

	// Global flags
	rootCmd.PersistentFlags().BoolVar(&jsonOutput, "json", false, "Output in JSON format")
	rootCmd.PersistentFlags().BoolVar(&verbose, "verbose", false, "Verbose output")

	// Add commands
	rootCmd.AddCommand(newAddCommand())
	rootCmd.AddCommand(newRemoveCommand())
	rootCmd.AddCommand(newUpdateCommand())
	rootCmd.AddCommand(newStatusCommand())
	rootCmd.AddCommand(newListCommand())
	rootCmd.AddCommand(newShowCommand())
	rootCmd.AddCommand(newSearchCommand())
	rootCmd.AddCommand(newImportCommand())
	rootCmd.AddCommand(newVersionCommand())

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func newAddCommand() *cobra.Command {
	var opts AddOptions
	cmd := &cobra.Command{
		Use:   "add <hostname>",
		Short: "Add a new host to the inventory",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			opts.Hostname = args[0]
			return runAdd(&opts)
		},
	}

	cmd.Flags().StringVar(&opts.IP, "ip", "", "IP address (required)")
	cmd.Flags().StringVar(&opts.Type, "type", "server", "Host type (server, container, vm, k8s-node, load-balancer, database)")
	cmd.Flags().StringVar(&opts.Provider, "provider", "other", "Cloud provider (oci, gcp, onprem, other)")
	cmd.Flags().StringVar(&opts.Region, "region", "", "Region/datacenter")
	cmd.Flags().StringVar(&opts.Size, "size", "", "Instance size")
	cmd.Flags().StringVar(&opts.Shape, "shape", "", "Instance shape")
	cmd.Flags().StringVar(&opts.Environment, "env", "development", "Environment (production, staging, development)")
	cmd.Flags().StringVar(&opts.Status, "status", "build", "Status (active, inactive, build, blackout, maintenance)")
	cmd.Flags().StringVar(&opts.Owners, "owners", "", "Comma-separated owner emails")
	cmd.Flags().StringVar(&opts.MailGroups, "mailgroups", "", "Comma-separated mail groups")
	cmd.Flags().Float64Var(&opts.CostDaily, "cost-daily", 0, "Average daily cost")
	cmd.Flags().Float64Var(&opts.CostMonthly, "cost-monthly", 0, "Average monthly cost")
	cmd.Flags().StringVar(&opts.Tags, "tags", "", "Tags as JSON object")
	cmd.Flags().StringVar(&opts.ExternalID, "external-id", "", "External resource ID")
	cmd.Flags().StringVar(&opts.ExternalURL, "external-url", "", "External resource URL")

	cmd.MarkFlagRequired("ip")

	return cmd
}

func newRemoveCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "remove <hostname>",
		Short: "Remove a host from the inventory",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return runRemove(args[0])
		},
	}
	return cmd
}

func newUpdateCommand() *cobra.Command {
	var opts UpdateOptions
	cmd := &cobra.Command{
		Use:   "update <hostname>",
		Short: "Update an existing host",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			opts.Hostname = args[0]
			return runUpdate(&opts)
		},
	}

	cmd.Flags().StringVar(&opts.IP, "ip", "", "IP address")
	cmd.Flags().StringVar(&opts.Type, "type", "", "Host type")
	cmd.Flags().StringVar(&opts.Provider, "provider", "", "Cloud provider")
	cmd.Flags().StringVar(&opts.Region, "region", "", "Region/datacenter")
	cmd.Flags().StringVar(&opts.Size, "size", "", "Instance size")
	cmd.Flags().StringVar(&opts.Shape, "shape", "", "Instance shape")
	cmd.Flags().StringVar(&opts.Environment, "env", "", "Environment")
	cmd.Flags().StringVar(&opts.Status, "status", "", "Status")
	cmd.Flags().StringVar(&opts.Owners, "owners", "", "Comma-separated owner emails")
	cmd.Flags().StringVar(&opts.MailGroups, "mailgroups", "", "Comma-separated mail groups")
	cmd.Flags().Float64Var(&opts.CostDaily, "cost-daily", -1, "Average daily cost")
	cmd.Flags().Float64Var(&opts.CostMonthly, "cost-monthly", -1, "Average monthly cost")
	cmd.Flags().StringVar(&opts.Tags, "tags", "", "Tags as JSON object")
	cmd.Flags().StringVar(&opts.ExternalID, "external-id", "", "External resource ID")
	cmd.Flags().StringVar(&opts.ExternalURL, "external-url", "", "External resource URL")

	return cmd
}

func newStatusCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "status <hostname> <new_status>",
		Short: "Update host status",
		Long:  "Update host status (active, inactive, build, blackout, maintenance, decommissioned)",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			return runStatus(args[0], args[1])
		},
	}
	return cmd
}

func newListCommand() *cobra.Command {
	var opts ListOptions
	cmd := &cobra.Command{
		Use:   "list",
		Short: "List hosts from inventory",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runList(&opts)
		},
	}

	cmd.Flags().StringVar(&opts.Status, "status", "", "Filter by status")
	cmd.Flags().StringVar(&opts.Environment, "env", "", "Filter by environment")
	cmd.Flags().StringVar(&opts.Type, "type", "", "Filter by type")
	cmd.Flags().StringVar(&opts.Provider, "provider", "", "Filter by provider")
	cmd.Flags().StringVar(&opts.Region, "region", "", "Filter by region")
	cmd.Flags().IntVar(&opts.Limit, "limit", 100, "Maximum number of results")

	return cmd
}

func newShowCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "show <hostname>",
		Short: "Show detailed information about a host",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return runShow(args[0])
		},
	}
	return cmd
}

func newSearchCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "search <query>",
		Short: "Search hosts by name, IP, or tags",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSearch(args[0])
		},
	}
	return cmd
}

func newVersionCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "version",
		Short: "Print version information",
		Run: func(cmd *cobra.Command, args []string) {
			if jsonOutput {
				printJSON(map[string]string{
					"version": version,
					"buildDate": buildDate,
				})
			} else {
				fmt.Printf("hostctl version %s (built %s)\n", version, buildDate)
			}
		},
	}
	return cmd
}

// printJSON prints data as JSON
func printJSON(data interface{}) error {
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	return encoder.Encode(data)
}

// printSuccess prints a success message
func printSuccess(msg string) {
	if jsonOutput {
		printJSON(map[string]interface{}{
			"success": true,
			"message": msg,
			"timestamp": time.Now().Format(time.RFC3339),
		})
	} else {
		fmt.Printf("%s%s%s\n", colorGreen, msg, colorReset)
	}
}

// printError prints an error message
func printError(msg string) {
	if jsonOutput {
		printJSON(map[string]interface{}{
			"success": false,
			"error": msg,
			"timestamp": time.Now().Format(time.RFC3339),
		})
	} else {
		fmt.Fprintf(os.Stderr, "%sError: %s%s\n", colorRed, msg, colorReset)
	}
}

// parseOwners parses comma-separated owners into a slice
func parseOwners(owners string) []string {
	if owners == "" {
		return []string{}
	}
	parts := strings.Split(owners, ",")
	result := make([]string, 0, len(parts))
	for _, p := range parts {
		if trimmed := strings.TrimSpace(p); trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

// parseTags parses JSON tags string into a map
func parseTags(tags string) (map[string]interface{}, error) {
	if tags == "" {
		return map[string]interface{}{}, nil
	}
	var result map[string]interface{}
	if err := json.Unmarshal([]byte(tags), &result); err != nil {
		return nil, fmt.Errorf("invalid JSON tags: %v", err)
	}
	return result, nil
}
