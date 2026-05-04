package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/spf13/cobra"
)

// SSHHost represents a parsed entry from ~/.ssh/config
type SSHHost struct {
	Name         string
	HostName     string // actual hostname or IP from HostName directive
	User         string
	Port         string
	IdentityFile string
}

// ProbeResult holds information discovered by SSHing into a host
type ProbeResult struct {
	Host          SSHHost
	IP            string
	OS            string   // rocky, debian, ubuntu, unknown
	OSVersion     string
	Kernel        string
	HasDocker     bool
	DockerVersion string
	HasK3s        bool
	K3sVersion    string
	Reachable     bool
	Error         string
}

// ImportOptions holds options for the import command
type ImportOptions struct {
	ConfigFile string
	Probe      bool
	DryRun     bool
	Update     bool
	Timeout    int
	Provider   string
	Env        string
}

func newImportCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "import",
		Short: "Import hosts from external sources",
	}
	cmd.AddCommand(newImportSSHConfigCommand())
	return cmd
}

func newImportSSHConfigCommand() *cobra.Command {
	var opts ImportOptions

	cmd := &cobra.Command{
		Use:   "ssh-config",
		Short: "Import hosts from ~/.ssh/config into the inventory",
		Long: `Parse SSH config file and add each Host entry to the hostctl inventory.

With --probe, SSH into each host to detect OS (Rocky Linux, Debian, Ubuntu),
Docker presence, and k3s presence, storing capabilities in metadata.

Examples:
  hostctl import ssh-config
  hostctl import ssh-config --probe --dry-run
  hostctl import ssh-config --file /etc/ssh/ssh_config --probe --update
`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runImportSSHConfig(&opts)
		},
	}

	home, _ := os.UserHomeDir()
	cmd.Flags().StringVar(&opts.ConfigFile, "file", filepath.Join(home, ".ssh", "config"), "Path to SSH config file")
	cmd.Flags().BoolVar(&opts.Probe, "probe", false, "SSH into each host to detect OS, Docker, k3s")
	cmd.Flags().BoolVar(&opts.DryRun, "dry-run", false, "Print what would be imported without writing")
	cmd.Flags().BoolVar(&opts.Update, "update", false, "Update existing hosts (default: skip existing)")
	cmd.Flags().IntVar(&opts.Timeout, "timeout", 10, "SSH probe timeout in seconds")
	cmd.Flags().StringVar(&opts.Provider, "provider", "onprem", "Default provider for imported hosts (oci, gcp, onprem, other)")
	cmd.Flags().StringVar(&opts.Env, "env", "production", "Default environment for imported hosts")

	return cmd
}

func runImportSSHConfig(opts *ImportOptions) error {
	hosts, err := parseSSHConfig(opts.ConfigFile)
	if err != nil {
		return fmt.Errorf("failed to parse SSH config: %w", err)
	}

	if len(hosts) == 0 {
		fmt.Println("No hosts found in SSH config.")
		return nil
	}

	fmt.Printf("Found %d host(s) in %s\n\n", len(hosts), opts.ConfigFile)

	var results []ProbeResult
	if opts.Probe {
		fmt.Println("Probing hosts (this may take a moment)...")
		results = probeHosts(hosts, opts.Timeout)
	} else {
		for _, h := range hosts {
			results = append(results, ProbeResult{Host: h, IP: h.HostName, Reachable: true})
		}
	}

	added, updated, skipped, failed := 0, 0, 0, 0

	for _, r := range results {
		hostname := r.Host.Name

		if opts.Probe && !r.Reachable {
			fmt.Printf("  %s%-30s%s UNREACHABLE: %s\n", colorRed, hostname, colorReset, r.Error)
			failed++
			continue
		}

		ip := r.IP
		if ip == "" {
			ip = r.Host.HostName
		}
		if ip == "" {
			ip = hostname
		}

		// Resolve IP if it looks like a hostname
		if net.ParseIP(ip) == nil {
			addrs, err := net.LookupHost(ip)
			if err == nil && len(addrs) > 0 {
				ip = addrs[0]
			}
		}

		provider := opts.Provider
		osType := r.OS

		// Build metadata
		meta := map[string]interface{}{
			"ip":          ip,
			"ssh_name":    r.Host.Name,
			"import_time": time.Now().UTC().Format(time.RFC3339),
		}
		if r.Host.User != "" {
			meta["ssh_user"] = r.Host.User
		}
		if r.Host.Port != "" && r.Host.Port != "22" {
			meta["ssh_port"] = r.Host.Port
		}
		if r.Host.IdentityFile != "" {
			meta["ssh_key"] = r.Host.IdentityFile
		}
		if osType != "" {
			meta["os"] = osType
		}
		if r.OSVersion != "" {
			meta["os_version"] = r.OSVersion
		}
		if r.Kernel != "" {
			meta["kernel"] = r.Kernel
		}
		if r.HasDocker {
			meta["has_docker"] = true
			if r.DockerVersion != "" {
				meta["docker_version"] = r.DockerVersion
			}
		}
		if r.HasK3s {
			meta["has_k3s"] = true
			if r.K3sVersion != "" {
				meta["k3s_version"] = r.K3sVersion
			}
		}

		metaJSON, _ := json.Marshal(meta)

		if opts.DryRun {
			fmt.Printf("  %s[DRY-RUN]%s %-30s ip=%-16s os=%-8s docker=%-5v k3s=%-5v\n",
				colorCyan, colorReset, hostname, ip, osType,
				r.HasDocker, r.HasK3s)
			continue
		}

		// Check if host already exists
		existing, lookupErr := getResourceByHostname(hostname)

		if lookupErr == nil && existing != nil {
			if !opts.Update {
				fmt.Printf("  %sSKIP%s    %-30s (already exists, use --update to overwrite)\n",
					colorYellow, colorReset, hostname)
				skipped++
				continue
			}

			// Update existing host
			updateOpts := &UpdateOptions{
				Hostname: hostname,
				IP:       ip,
				Provider: provider,
				Tags:     string(metaJSON),
			}
			if osType != "" {
				updateOpts.Tags = string(metaJSON)
			}
			_, err := updateResource(updateOpts)
			if err != nil {
				fmt.Printf("  %sFAIL%s    %-30s %v\n", colorRed, colorReset, hostname, err)
				failed++
				continue
			}
			fmt.Printf("  %sUPDATED%s  %-30s ip=%-16s os=%s\n",
				colorBlue, colorReset, hostname, ip, osType)
			updated++
		} else {
			// Add new host
			addOpts := &AddOptions{
				Hostname:    hostname,
				IP:          ip,
				Type:        "server",
				Provider:    provider,
				Environment: opts.Env,
				Status:      "active",
				Tags:        string(metaJSON),
			}
			_, err := insertResource(addOpts)
			if err != nil {
				fmt.Printf("  %sFAIL%s    %-30s %v\n", colorRed, colorReset, hostname, err)
				failed++
				continue
			}
			fmt.Printf("  %sADDED%s    %-30s ip=%-16s os=%s\n",
				colorGreen, colorReset, hostname, ip, osType)
			added++
		}
	}

	if !opts.DryRun {
		fmt.Printf("\nSummary: %sadded=%d%s  %supdated=%d%s  %sskipped=%d%s  %sfailed=%d%s\n",
			colorGreen, added, colorReset,
			colorBlue, updated, colorReset,
			colorYellow, skipped, colorReset,
			colorRed, failed, colorReset)
	}

	return nil
}

// parseSSHConfig parses an SSH config file and returns a list of hosts.
// Handles Include directives by recursively parsing included files.
func parseSSHConfig(path string) ([]SSHHost, error) {
	return parseSSHConfigFile(path, make(map[string]bool))
}

func parseSSHConfigFile(path string, seen map[string]bool) ([]SSHHost, error) {
	abs, err := filepath.Abs(path)
	if err != nil {
		return nil, err
	}
	if seen[abs] {
		return nil, nil
	}
	seen[abs] = true

	f, err := os.Open(abs)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var hosts []SSHHost
	var current *SSHHost

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())

		// Skip comments and blanks
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		// Split into keyword and value
		parts := strings.SplitN(line, " ", 2)
		if len(parts) < 2 {
			parts = strings.SplitN(line, "=", 2)
		}
		if len(parts) < 2 {
			continue
		}
		keyword := strings.ToLower(strings.TrimSpace(parts[0]))
		value := strings.TrimSpace(parts[1])

		switch keyword {
		case "include":
			// Expand glob patterns relative to ~/.ssh/
			if !filepath.IsAbs(value) {
				home, _ := os.UserHomeDir()
				value = filepath.Join(home, ".ssh", value)
			}
			matches, _ := filepath.Glob(value)
			for _, m := range matches {
				sub, _ := parseSSHConfigFile(m, seen)
				hosts = append(hosts, sub...)
			}

		case "host":
			// Save previous host
			if current != nil && !isWildcard(current.Name) {
				hosts = append(hosts, *current)
			}
			// Start new host — skip wildcard patterns
			if !isWildcard(value) {
				current = &SSHHost{Name: value}
			} else {
				current = nil
			}

		case "hostname":
			if current != nil {
				current.HostName = value
			}
		case "user":
			if current != nil {
				current.User = value
			}
		case "port":
			if current != nil {
				current.Port = value
			}
		case "identityfile":
			if current != nil {
				// Expand ~ in identity file path
				if strings.HasPrefix(value, "~/") {
					home, _ := os.UserHomeDir()
					value = filepath.Join(home, value[2:])
				}
				current.IdentityFile = value
			}
		}
	}

	// Save last host
	if current != nil && !isWildcard(current.Name) {
		hosts = append(hosts, *current)
	}

	return hosts, scanner.Err()
}

func isWildcard(name string) bool {
	return strings.ContainsAny(name, "*?!")
}

// probeHosts SSH probes each host concurrently with a bounded worker pool.
func probeHosts(hosts []SSHHost, timeoutSecs int) []ProbeResult {
	results := make([]ProbeResult, len(hosts))
	sem := make(chan struct{}, 8) // max 8 concurrent SSH probes

	type indexedResult struct {
		idx    int
		result ProbeResult
	}
	ch := make(chan indexedResult, len(hosts))

	for i, h := range hosts {
		go func(idx int, host SSHHost) {
			sem <- struct{}{}
			defer func() { <-sem }()
			ch <- indexedResult{idx: idx, result: probeHost(host, timeoutSecs)}
		}(i, h)
	}

	for range hosts {
		r := <-ch
		results[r.idx] = r.result
	}
	return results
}

// probeHost SSHes into a host and runs a single multi-part probe script.
func probeHost(host SSHHost, timeoutSecs int) ProbeResult {
	result := ProbeResult{Host: host}

	// Determine target address
	target := host.HostName
	if target == "" {
		target = host.Name
	}

	// Build SSH args
	sshArgs := []string{
		"-o", "StrictHostKeyChecking=accept-new",
		"-o", fmt.Sprintf("ConnectTimeout=%d", timeoutSecs),
		"-o", "BatchMode=yes",
	}
	if host.Port != "" && host.Port != "22" {
		sshArgs = append(sshArgs, "-p", host.Port)
	}
	if host.IdentityFile != "" {
		sshArgs = append(sshArgs, "-i", host.IdentityFile)
	}
	if host.User != "" {
		target = host.User + "@" + target
	}
	sshArgs = append(sshArgs, target)

	// Probe script — runs as a single SSH connection
	probeScript := `
set -e
echo "IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo '')"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "OS_ID=${ID:-unknown}"
    echo "OS_VERSION=${VERSION_ID:-unknown}"
    echo "OS_NAME=${PRETTY_NAME:-unknown}"
fi
echo "KERNEL=$(uname -r 2>/dev/null || echo '')"
if command -v docker >/dev/null 2>&1; then
    echo "DOCKER=1"
    echo "DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'unknown')"
else
    echo "DOCKER=0"
fi
if command -v k3s >/dev/null 2>&1; then
    echo "K3S=1"
    echo "K3S_VERSION=$(k3s --version 2>/dev/null | head -1 | awk '{print $3}' || echo 'unknown')"
elif [ -f /usr/local/bin/k3s ]; then
    echo "K3S=1"
    echo "K3S_VERSION=$(k3s --version 2>/dev/null | head -1 | awk '{print $3}' || echo 'unknown')"
else
    echo "K3S=0"
fi
`

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSecs+5)*time.Second)
	defer cancel()

	args := append(sshArgs, probeScript)
	out, err := exec.CommandContext(ctx, "ssh", args...).Output()
	if err != nil {
		result.Reachable = false
		result.Error = err.Error()
		return result
	}

	result.Reachable = true

	// Parse key=value output from probe script
	for _, line := range strings.Split(string(out), "\n") {
		line = strings.TrimSpace(line)
		kv := strings.SplitN(line, "=", 2)
		if len(kv) != 2 {
			continue
		}
		k, v := kv[0], strings.Trim(kv[1], "'\"")
		switch k {
		case "IP":
			if v != "" {
				result.IP = v
			}
		case "OS_ID":
			switch strings.ToLower(v) {
			case "rocky":
				result.OS = "rocky"
			case "rhel", "centos", "almalinux", "fedora":
				result.OS = "rhel-like"
			case "debian":
				result.OS = "debian"
			case "ubuntu":
				result.OS = "ubuntu"
			default:
				result.OS = v
			}
		case "OS_VERSION":
			result.OSVersion = v
		case "KERNEL":
			result.Kernel = v
		case "DOCKER":
			result.HasDocker = v == "1"
		case "DOCKER_VERSION":
			result.DockerVersion = v
		case "K3S":
			result.HasK3s = v == "1"
		case "K3S_VERSION":
			result.K3sVersion = v
		}
	}

	return result
}

// printSuccess, printError, and printJSON are defined in main.go
