package cmd

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

// NewK3sCommand returns the `k3s` subcommand tree.
func NewK3sCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "k3s",
		Short: "Manage k3s clusters on remote hosts",
		Long:  "Run k3s / kubectl commands on remote baremetal hosts over SSH.",
	}

	cmd.AddCommand(newK3sNodesCommand())
	cmd.AddCommand(newK3sPodsCommand())
	cmd.AddCommand(newK3sServicesCommand())
	cmd.AddCommand(newK3sDeploymentsCommand())
	cmd.AddCommand(newK3sLogsCommand())
	cmd.AddCommand(newK3sApplyCommand())
	cmd.AddCommand(newK3sDeleteCommand())
	cmd.AddCommand(newK3sKubeconfigCommand())
	cmd.AddCommand(newK3sExecCommand())
	cmd.AddCommand(newK3sGetCommand())
	cmd.AddCommand(newK3sDescribeCommand())
	cmd.AddCommand(newK3sTopCommand())

	return cmd
}

// kubectl runs a kubectl command via k3s kubectl on the remote host.
// k3s bundles kubectl, so `k3s kubectl` is always available where k3s is installed.
func kubectl(hostname, ns, subcmd string) error {
	nsFlag := ""
	if ns == "all" || ns == "--all-namespaces" {
		nsFlag = "-A"
	} else if ns != "" {
		nsFlag = "-n " + ns
	}
	return k3sRun(hostname, "k3s kubectl "+subcmd+" "+nsFlag)
}

func k3sRun(hostname, cmd string) error {
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

func k3sStream(hostname, cmd string) error {
	ex, err := executorFor(hostname)
	if err != nil {
		return err
	}
	return ex.Stream(context.Background(), cmd, os.Stdout, os.Stderr)
}

func newK3sNodesCommand() *cobra.Command {
	var wide bool
	cmd := &cobra.Command{
		Use:   "nodes <host>",
		Short: "List k3s nodes",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			flags := "get nodes"
			if wide {
				flags += " -o wide"
			}
			return k3sRun(args[0], "k3s kubectl "+flags)
		},
	}
	cmd.Flags().BoolVarP(&wide, "wide", "w", false, "Show wide output")
	return cmd
}

func newK3sPodsCommand() *cobra.Command {
	var ns string
	var wide bool

	cmd := &cobra.Command{
		Use:   "pods <host>",
		Short: "List pods on a k3s cluster",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			flags := "get pods"
			if ns == "all" {
				flags += " -A"
			} else if ns != "" {
				flags += " -n " + ns
			} else {
				flags += " -A"
			}
			if wide {
				flags += " -o wide"
			}
			return k3sRun(args[0], "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "all", "Namespace (default: all)")
	cmd.Flags().BoolVarP(&wide, "wide", "w", false, "Wide output")
	return cmd
}

func newK3sServicesCommand() *cobra.Command {
	var ns string
	cmd := &cobra.Command{
		Use:     "services <host>",
		Aliases: []string{"svc"},
		Short:   "List services on a k3s cluster",
		Args:    cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			flags := "get services"
			if ns == "all" {
				flags += " -A"
			} else if ns != "" {
				flags += " -n " + ns
			} else {
				flags += " -A"
			}
			return k3sRun(args[0], "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "all", "Namespace")
	return cmd
}

func newK3sDeploymentsCommand() *cobra.Command {
	var ns string
	cmd := &cobra.Command{
		Use:     "deployments <host>",
		Aliases: []string{"deploy"},
		Short:   "List deployments on a k3s cluster",
		Args:    cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			flags := "get deployments"
			if ns == "all" {
				flags += " -A"
			} else if ns != "" {
				flags += " -n " + ns
			} else {
				flags += " -A"
			}
			return k3sRun(args[0], "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "all", "Namespace")
	return cmd
}

func newK3sLogsCommand() *cobra.Command {
	var ns string
	var follow bool
	var tail string
	var container string
	var previous bool

	cmd := &cobra.Command{
		Use:   "logs <host> <pod>",
		Short: "Fetch logs from a pod on a remote k3s host",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			flags := "logs " + args[1]
			if ns != "" {
				flags += " -n " + ns
			}
			if follow {
				flags += " -f"
			}
			if tail != "" {
				flags += " --tail=" + tail
			}
			if container != "" {
				flags += " -c " + container
			}
			if previous {
				flags += " -p"
			}
			return k3sStream(args[0], "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "", "Namespace")
	cmd.Flags().BoolVarP(&follow, "follow", "f", false, "Follow log output")
	cmd.Flags().StringVar(&tail, "tail", "100", "Lines from end")
	cmd.Flags().StringVarP(&container, "container", "c", "", "Container name")
	cmd.Flags().BoolVarP(&previous, "previous", "p", false, "Show previous container logs")
	return cmd
}

func newK3sApplyCommand() *cobra.Command {
	var file string

	cmd := &cobra.Command{
		Use:   "apply <host>",
		Short: "Apply a manifest to a remote k3s cluster",
		Long: `Copy a manifest to the remote host and apply it.

Example:
  infractl k3s apply web-01 -f ./deploy/myapp.yaml`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if file == "" {
				return fmt.Errorf("-f/--file is required")
			}
			return applyManifest(args[0], file, false)
		},
	}
	cmd.Flags().StringVarP(&file, "file", "f", "", "Path to manifest file (required)")
	return cmd
}

func newK3sDeleteCommand() *cobra.Command {
	var file string

	cmd := &cobra.Command{
		Use:   "delete <host>",
		Short: "Delete resources from a remote k3s cluster using a manifest",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if file == "" {
				return fmt.Errorf("-f/--file is required")
			}
			return applyManifest(args[0], file, true)
		},
	}
	cmd.Flags().StringVarP(&file, "file", "f", "", "Path to manifest file (required)")
	return cmd
}

func newK3sKubeconfigCommand() *cobra.Command {
	var merge bool
	var output string

	cmd := &cobra.Command{
		Use:   "kubeconfig <host>",
		Short: "Fetch kubeconfig from a remote k3s host",
		Long: `Download /etc/rancher/k3s/k3s.yaml and optionally merge it into ~/.kube/config.

The server address is rewritten to the host's reachable address.`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return fetchKubeconfig(args[0], merge, output)
		},
	}
	cmd.Flags().BoolVar(&merge, "merge", false, "Merge into ~/.kube/config")
	cmd.Flags().StringVarP(&output, "output", "o", "", "Write to file (default: stdout)")
	return cmd
}

func newK3sExecCommand() *cobra.Command {
	var ns string
	var container string

	cmd := &cobra.Command{
		Use:   "exec <host> <pod> -- <command...>",
		Short: "Execute a command in a pod on a remote k3s host",
		Args:  cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			host := args[0]
			pod := args[1]
			execCmd := "sh"
			if len(args) > 2 {
				execCmd = strings.Join(args[2:], " ")
			}
			flags := fmt.Sprintf("exec -it %s", pod)
			if ns != "" {
				flags += " -n " + ns
			}
			if container != "" {
				flags += " -c " + container
			}
			flags += " -- " + execCmd
			return k3sStream(host, "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "", "Namespace")
	cmd.Flags().StringVarP(&container, "container", "c", "", "Container")
	return cmd
}

func newK3sGetCommand() *cobra.Command {
	var ns string
	var output string

	cmd := &cobra.Command{
		Use:   "get <host> <resource> [name]",
		Short: "Get k3s resources (pods, nodes, services, deployments, etc.)",
		Args:  cobra.MinimumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			host := args[0]
			resource := strings.Join(args[1:], " ")
			flags := "get " + resource
			if ns == "all" {
				flags += " -A"
			} else if ns != "" {
				flags += " -n " + ns
			}
			if output != "" {
				flags += " -o " + output
			}
			return k3sRun(host, "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "", "Namespace (all = -A)")
	cmd.Flags().StringVarP(&output, "output", "o", "", "Output format (json, yaml, wide)")
	return cmd
}

func newK3sDescribeCommand() *cobra.Command {
	var ns string
	cmd := &cobra.Command{
		Use:   "describe <host> <resource> <name>",
		Short: "Describe a k3s resource",
		Args:  cobra.MinimumNArgs(3),
		RunE: func(cmd *cobra.Command, args []string) error {
			host := args[0]
			flags := "describe " + strings.Join(args[1:], " ")
			if ns != "" {
				flags += " -n " + ns
			}
			return k3sRun(host, "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "", "Namespace")
	return cmd
}

func newK3sTopCommand() *cobra.Command {
	var ns string
	cmd := &cobra.Command{
		Use:   "top <host> (nodes|pods)",
		Short: "Show resource usage for nodes or pods",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			flags := "top " + args[1]
			if ns != "" {
				flags += " -n " + ns
			}
			return k3sRun(args[0], "k3s kubectl "+flags)
		},
	}
	cmd.Flags().StringVarP(&ns, "namespace", "n", "", "Namespace")
	return cmd
}

// applyManifest copies a local manifest to the remote host and applies/deletes it.
func applyManifest(hostname, localFile string, delete bool) error {
	ex, err := executorFor(hostname)
	if err != nil {
		return err
	}

	// Copy file to a temp location on the remote host
	remoteTmp := "/tmp/infractl-manifest-" + strings.ReplaceAll(localFile, "/", "_")
	ctx := context.Background()

	fmt.Printf("Copying %s → %s:%s\n", localFile, hostname, remoteTmp)
	if err := ex.ScpTo(ctx, localFile, remoteTmp); err != nil {
		return fmt.Errorf("scp: %w", err)
	}

	verb := "apply"
	if delete {
		verb = "delete"
	}

	cmd := fmt.Sprintf("k3s kubectl %s -f %s && rm -f %s", verb, remoteTmp, remoteTmp)
	return k3sStream(hostname, cmd)
}

// fetchKubeconfig downloads /etc/rancher/k3s/k3s.yaml and rewrites the server address.
func fetchKubeconfig(hostname string, merge bool, outputFile string) error {
	_ = merge // --merge flag reserved for future kubeconfig merge logic
	ex, err := executorFor(hostname)
	if err != nil {
		return err
	}

	// Get the resolved host address to replace 127.0.0.1 in the kubeconfig
	h, err := resolveHost(hostname)
	if err != nil {
		return err
	}

	serverAddr := h.Target
	if serverAddr == "" {
		serverAddr = hostname
	}

	ctx := context.Background()
	// Read the kubeconfig and rewrite the server address
	cmd := fmt.Sprintf(
		`sudo cat /etc/rancher/k3s/k3s.yaml | sed 's|https://127.0.0.1|https://%s|g'`,
		serverAddr,
	)

	out, err := ex.Run(ctx, cmd)
	if err != nil {
		return fmt.Errorf("read kubeconfig: %w", err)
	}

	if outputFile != "" {
		if err := os.WriteFile(outputFile, []byte(out), 0600); err != nil {
			return fmt.Errorf("write %s: %w", outputFile, err)
		}
		fmt.Printf("Wrote kubeconfig to %s\n", outputFile)
	} else {
		fmt.Print(out)
	}
	return nil
}
