package cmd

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

// NewDockerCommand returns the `docker` subcommand tree.
func NewDockerCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "docker",
		Short: "Manage Docker containers on remote hosts",
		Long:  "Run Docker commands on remote baremetal/VM hosts over SSH.",
	}

	cmd.AddCommand(newDockerLsCommand())
	cmd.AddCommand(newDockerStartCommand())
	cmd.AddCommand(newDockerStopCommand())
	cmd.AddCommand(newDockerRestartCommand())
	cmd.AddCommand(newDockerRmCommand())
	cmd.AddCommand(newDockerLogsCommand())
	cmd.AddCommand(newDockerExecCommand())
	cmd.AddCommand(newDockerPullCommand())
	cmd.AddCommand(newDockerStatsCommand())
	cmd.AddCommand(newDockerRunCommand())

	return cmd
}

func newDockerLsCommand() *cobra.Command {
	var all bool
	return &cobra.Command{
		Use:     "ls <host>",
		Aliases: []string{"ps", "list"},
		Short:   "List containers on a remote host",
		Args:    cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := `table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}`
			if all {
				return dockerRun(args[0], "docker ps -a --format '"+format+"'")
			}
			return dockerRun(args[0], "docker ps --format '"+format+"'")
		},
	}
}

// nolint flag defined but not wired — add with PersistentPreRunE if needed
func init() {}

func newDockerStartCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "start <host> <container> [container...]",
		Short: "Start one or more containers on a remote host",
		Args:  cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			containers := strings.Join(args[1:], " ")
			return dockerRun(args[0], "docker start "+containers)
		},
	}
}

func newDockerStopCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "stop <host> <container> [container...]",
		Short: "Stop one or more containers on a remote host",
		Args:  cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			containers := strings.Join(args[1:], " ")
			return dockerRun(args[0], "docker stop "+containers)
		},
	}
}

func newDockerRestartCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "restart <host> <container> [container...]",
		Short: "Restart one or more containers on a remote host",
		Args:  cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			containers := strings.Join(args[1:], " ")
			return dockerRun(args[0], "docker restart "+containers)
		},
	}
}

func newDockerRmCommand() *cobra.Command {
	var force bool
	cmd := &cobra.Command{
		Use:   "rm <host> <container> [container...]",
		Short: "Remove one or more containers on a remote host",
		Args:  cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			flag := ""
			if force {
				flag = "-f "
			}
			containers := strings.Join(args[1:], " ")
			return dockerRun(args[0], "docker rm "+flag+containers)
		},
	}
	cmd.Flags().BoolVarP(&force, "force", "f", false, "Force remove running container")
	return cmd
}

func newDockerLogsCommand() *cobra.Command {
	var follow bool
	var tail string
	var since string

	cmd := &cobra.Command{
		Use:   "logs <host> <container>",
		Short: "Fetch logs from a container on a remote host",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			flags := ""
			if follow {
				flags += " -f"
			}
			if tail != "" {
				flags += " --tail " + tail
			}
			if since != "" {
				flags += " --since " + since
			}
			return dockerStream(args[0], "docker logs"+flags+" "+args[1])
		},
	}
	cmd.Flags().BoolVarP(&follow, "follow", "f", false, "Follow log output")
	cmd.Flags().StringVar(&tail, "tail", "100", "Number of lines to show from end")
	cmd.Flags().StringVar(&since, "since", "", "Show logs since timestamp (e.g. 2h, 2024-01-01)")
	return cmd
}

func newDockerExecCommand() *cobra.Command {
	var interactive bool

	cmd := &cobra.Command{
		Use:   "exec <host> <container> [command...]",
		Short: "Run a command in a container on a remote host",
		Args:  cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			host := args[0]
			container := args[1]
			execCmd := "sh"
			if len(args) > 2 {
				execCmd = strings.Join(args[2:], " ")
			}
			flag := ""
			if interactive {
				flag = "-it "
			}
			return dockerStream(host, "docker exec "+flag+container+" "+execCmd)
		},
	}
	cmd.Flags().BoolVarP(&interactive, "interactive", "i", false, "Keep stdin open")
	return cmd
}

func newDockerPullCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "pull <host> <image>",
		Short: "Pull a Docker image on a remote host",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			return dockerRun(args[0], "docker pull "+args[1])
		},
	}
}

func newDockerStatsCommand() *cobra.Command {
	var noStream bool
	cmd := &cobra.Command{
		Use:   "stats <host>",
		Short: "Display live resource usage for containers on a remote host",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			flag := ""
			if noStream {
				flag = "--no-stream "
			}
			return dockerStream(args[0], "docker stats "+flag)
		},
	}
	cmd.Flags().BoolVar(&noStream, "no-stream", true, "Disable streaming stats (show one snapshot)")
	return cmd
}

func newDockerRunCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "run <host> -- <docker-run-args...>",
		Short: "Run a docker run command on a remote host",
		Long: `Pass docker run arguments directly.

Example:
  infractl docker run web-01 -- -d --name myapp -p 8080:80 nginx:alpine`,
		DisableFlagParsing: true,
		Args:               cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			host := args[0]
			// Strip '--' separator if present
			rest := args[1:]
			if len(rest) > 0 && rest[0] == "--" {
				rest = rest[1:]
			}
			return dockerRun(host, "docker run "+strings.Join(rest, " "))
		},
	}
}

// dockerRun runs a docker command on a remote host and prints output.
func dockerRun(hostname, cmd string) error {
	ex, err := executorFor(hostname)
	if err != nil {
		return err
	}
	out, err := ex.Run(context.Background(), cmd)
	fmt.Print(out)
	if err != nil && strings.TrimSpace(out) == "" {
		return fmt.Errorf("ssh: %w", err)
	}
	return nil
}

// dockerStream runs a docker command with streaming I/O (for logs -f, exec, stats).
func dockerStream(hostname, cmd string) error {
	ex, err := executorFor(hostname)
	if err != nil {
		return err
	}
	return ex.Stream(context.Background(), cmd, os.Stdout, os.Stderr)
}
