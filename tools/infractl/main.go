package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"github.com/afterdarksys/adsops-utils/tools/infractl/cmd"
)

var version = "1.0.0"

func main() {
	root := &cobra.Command{
		Use:     "infractl",
		Short:   "Docker and k3s management for remote baremetal hosts",
		Version: version,
		Long: `infractl manages Docker containers and k3s clusters on remote hosts over SSH.

It uses the hostctl inventory (when configured) to resolve host→IP/key,
falling back to ~/.ssh/config entries. All commands work with Rocky Linux,
Debian, and Ubuntu hosts.

Examples:
  infractl scan --all                       Probe all hosts
  infractl status web-01                    Docker + k3s overview
  infractl docker ls web-01                 List containers
  infractl docker logs web-01 myapp -f      Follow container logs
  infractl k3s pods web-01                  List pods
  infractl k3s apply web-01 -f deploy.yaml  Apply a manifest`,
		PersistentPreRun: func(cmd_ *cobra.Command, args []string) {
			// Global flags are set before any subcommand runs
		},
	}

	// Global flags
	root.PersistentFlags().IntVar(&cmd.Global.Timeout, "timeout", 15, "SSH command timeout in seconds")
	root.PersistentFlags().BoolVarP(&cmd.Global.Verbose, "verbose", "v", false, "Verbose SSH output")

	// Subcommands
	root.AddCommand(cmd.NewScanCommand())
	root.AddCommand(cmd.NewStatusCommand())
	root.AddCommand(cmd.NewDockerCommand())
	root.AddCommand(cmd.NewK3sCommand())

	if err := root.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
