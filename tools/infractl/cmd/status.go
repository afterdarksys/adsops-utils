package cmd

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/spf13/cobra"

	"github.com/afterdarksys/adsops-utils/tools/infractl/inventory"
)

// NewStatusCommand returns the `status` subcommand.
func NewStatusCommand() *cobra.Command {
	var all bool

	cmd := &cobra.Command{
		Use:   "status [host...]",
		Short: "Show Docker and k3s status overview for one or more hosts",
		Long: `Display a concise status overview including:
  - Docker: containers running / total
  - k3s: nodes ready / total, pods running / total

Examples:
  infractl status web-01
  infractl status --all`,
		RunE: func(cmd *cobra.Command, args []string) error {
			if !all && len(args) == 0 {
				return fmt.Errorf("specify host(s) or use --all")
			}
			var hosts []*inventory.HostRecord
			if all {
				var err error
				hosts, err = allHosts()
				if err != nil {
					return fmt.Errorf("list hosts: %w", err)
				}
			} else {
				for _, name := range args {
					hosts = append(hosts, &inventory.HostRecord{Hostname: name})
				}
			}
			return runStatus(hosts)
		},
	}

	cmd.Flags().BoolVarP(&all, "all", "a", false, "Query all known hosts")
	return cmd
}

type hostStatus struct {
	hostname        string
	ok              bool
	err             string
	dockerRunning   int
	dockerTotal     int
	k3sReady        int
	k3sTotal        int
	k3sPodRunning   int
	k3sPodTotal     int
}

var statusScript = `
DOCKER_RUNNING=0; DOCKER_TOTAL=0
if command -v docker >/dev/null 2>&1; then
    DOCKER_TOTAL=$(docker ps -a -q 2>/dev/null | wc -l | tr -d ' ')
    DOCKER_RUNNING=$(docker ps -q 2>/dev/null | wc -l | tr -d ' ')
fi
echo "DOCKER_RUNNING=$DOCKER_RUNNING"
echo "DOCKER_TOTAL=$DOCKER_TOTAL"

K3S_NODES_READY=0; K3S_NODES_TOTAL=0; K3S_PODS_RUNNING=0; K3S_PODS_TOTAL=0
if command -v k3s >/dev/null 2>&1 || [ -f /usr/local/bin/k3s ]; then
    K3S_NODES_TOTAL=$(k3s kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
    K3S_NODES_READY=$(k3s kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready" || true)
    K3S_PODS_TOTAL=$(k3s kubectl get pods -A --no-headers 2>/dev/null | wc -l | tr -d ' ')
    K3S_PODS_RUNNING=$(k3s kubectl get pods -A --no-headers 2>/dev/null | grep -c "Running" || true)
fi
echo "K3S_NODES_READY=$K3S_NODES_READY"
echo "K3S_NODES_TOTAL=$K3S_NODES_TOTAL"
echo "K3S_PODS_RUNNING=$K3S_PODS_RUNNING"
echo "K3S_PODS_TOTAL=$K3S_PODS_TOTAL"
`

func runStatus(hosts []*inventory.HostRecord) error {
	statuses := make([]hostStatus, len(hosts))
	var wg sync.WaitGroup
	sem := make(chan struct{}, 8)

	for i, h := range hosts {
		wg.Add(1)
		go func(idx int, hostname string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			statuses[idx] = fetchHostStatus(hostname)
		}(i, h.Hostname)
	}
	wg.Wait()

	fmt.Printf("\n%-24s %-6s %-20s %-20s\n", "HOST", "STATUS", "DOCKER (run/total)", "K3S (nodes/pods)")
	fmt.Println(strings.Repeat("─", 75))

	for _, s := range statuses {
		if !s.ok {
			fmt.Printf("%-24s %-6s %s\n", s.hostname, colorize("red", "FAIL"), colorize("red", s.err))
			continue
		}

		dockerStr := fmt.Sprintf("%d/%d containers", s.dockerRunning, s.dockerTotal)
		dockerCol := colorize("green", dockerStr)
		if s.dockerTotal == 0 {
			dockerCol = colorize("yellow", "not running")
		}

		k3sStr := fmt.Sprintf("%d/%d nodes  %d/%d pods", s.k3sReady, s.k3sTotal, s.k3sPodRunning, s.k3sPodTotal)
		k3sCol := colorize("green", k3sStr)
		if s.k3sTotal == 0 {
			k3sCol = colorize("yellow", "not running")
		}

		fmt.Printf("%-24s %-6s %-20s %-20s\n",
			s.hostname, colorize("green", "OK"), dockerCol, k3sCol)
	}
	fmt.Println()
	return nil
}

func fetchHostStatus(hostname string) hostStatus {
	s := hostStatus{hostname: hostname}

	ex, err := executorFor(hostname)
	if err != nil {
		s.err = err.Error()
		return s
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(Global.Timeout)*time.Second)
	defer cancel()

	out, err := ex.Run(ctx, statusScript)
	if err != nil {
		s.err = strings.TrimSpace(err.Error())
		return s
	}

	s.ok = true
	for _, line := range strings.Split(out, "\n") {
		kv := strings.SplitN(strings.TrimSpace(line), "=", 2)
		if len(kv) != 2 {
			continue
		}
		k, v := kv[0], kv[1]
		n := 0
		fmt.Sscanf(v, "%d", &n)
		switch k {
		case "DOCKER_RUNNING":
			s.dockerRunning = n
		case "DOCKER_TOTAL":
			s.dockerTotal = n
		case "K3S_NODES_READY":
			s.k3sReady = n
		case "K3S_NODES_TOTAL":
			s.k3sTotal = n
		case "K3S_PODS_RUNNING":
			s.k3sPodRunning = n
		case "K3S_PODS_TOTAL":
			s.k3sPodTotal = n
		}
	}
	return s
}
