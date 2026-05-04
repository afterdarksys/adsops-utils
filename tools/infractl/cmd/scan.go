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

// NewScanCommand returns the `scan` subcommand.
func NewScanCommand() *cobra.Command {
	var all bool

	cmd := &cobra.Command{
		Use:   "scan [host...]",
		Short: "Probe hosts to detect Docker, k3s, OS, and connectivity",
		Long: `SSH into one or more hosts and detect:
  - Operating system (Rocky Linux, Debian, Ubuntu)
  - Docker presence and version
  - k3s presence and version
  - statsagent presence

Examples:
  infractl scan web-01
  infractl scan --all
  infractl scan web-01 db-01 cache-01`,
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
			return runScan(hosts)
		},
	}

	cmd.Flags().BoolVarP(&all, "all", "a", false, "Scan all known hosts")
	return cmd
}

type scanResult struct {
	hostname string
	ok       bool
	os       string
	osVer    string
	docker   string // version or ""
	k3s      string // version or ""
	stats    bool   // statsagent running?
	err      string
}

var scanScript = `
set -e
OS_ID="unknown"; OS_VER="unknown"
if [ -f /etc/os-release ]; then . /etc/os-release; OS_ID="${ID:-unknown}"; OS_VER="${VERSION_ID:-unknown}"; fi
echo "OS_ID=$OS_ID"
echo "OS_VER=$OS_VER"
DOCKER_VER=""
if command -v docker >/dev/null 2>&1; then
    DOCKER_VER=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'installed')
fi
echo "DOCKER_VER=$DOCKER_VER"
K3S_VER=""
if command -v k3s >/dev/null 2>&1 || [ -f /usr/local/bin/k3s ]; then
    K3S_VER=$(k3s --version 2>/dev/null | head -1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+[^ ]*' || echo 'installed')
fi
echo "K3S_VER=$K3S_VER"
STATS="0"
if curl -sf http://localhost:9100/health >/dev/null 2>&1; then STATS="1"; fi
echo "STATS=$STATS"
`

func runScan(hosts []*inventory.HostRecord) error {
	results := make([]scanResult, len(hosts))
	var wg sync.WaitGroup
	sem := make(chan struct{}, 8)

	for i, h := range hosts {
		wg.Add(1)
		go func(idx int, hostname string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[idx] = scanHost(hostname)
		}(i, h.Hostname)
	}
	wg.Wait()

	// Print results table
	fmt.Printf("\n%-24s %-10s %-8s %-18s %-18s %-7s\n",
		"HOST", "STATUS", "OS", "DOCKER", "K3S", "STATS")
	fmt.Println(strings.Repeat("─", 90))

	for _, r := range results {
		status := colorize("green", "OK")
		if !r.ok {
			status = colorize("red", "FAIL")
		}

		osStr := r.os
		if r.osVer != "" {
			osStr += " " + r.osVer
		}

		dockerStr := colorize("yellow", "none")
		if r.docker != "" {
			dockerStr = colorize("green", r.docker)
		}

		k3sStr := colorize("yellow", "none")
		if r.k3s != "" {
			k3sStr = colorize("green", r.k3s)
		}

		statsStr := colorize("yellow", "no")
		if r.stats {
			statsStr = colorize("green", "yes")
		}

		if !r.ok {
			fmt.Printf("%-24s %-10s %s\n", r.hostname, status, colorize("red", r.err))
		} else {
			fmt.Printf("%-24s %-10s %-8s %-18s %-18s %-7s\n",
				r.hostname, status, osStr, dockerStr, k3sStr, statsStr)
		}
	}
	fmt.Println()

	return nil
}

func scanHost(hostname string) scanResult {
	r := scanResult{hostname: hostname}

	ex, err := executorFor(hostname)
	if err != nil {
		r.err = err.Error()
		return r
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(Global.Timeout)*time.Second)
	defer cancel()

	out, err := ex.Run(ctx, scanScript)
	if err != nil {
		r.err = strings.TrimSpace(err.Error())
		return r
	}

	r.ok = true
	for _, line := range strings.Split(out, "\n") {
		kv := strings.SplitN(strings.TrimSpace(line), "=", 2)
		if len(kv) != 2 {
			continue
		}
		k, v := kv[0], strings.Trim(kv[1], `"'`)
		switch k {
		case "OS_ID":
			r.os = v
		case "OS_VER":
			r.osVer = v
		case "DOCKER_VER":
			r.docker = v
		case "K3S_VER":
			r.k3s = v
		case "STATS":
			r.stats = v == "1"
		}
	}
	return r
}
