package cmd

import (
	"context"
	"encoding/base64"
	"fmt"
	"math"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/spf13/cobra"

	"github.com/afterdarksys/adsops-utils/tools/infractl/inventory"
	"github.com/afterdarksys/adsops-utils/tools/infractl/metrics"
)

const (
	defaultNEPort    = 9100
	defaultNEVersion = "1.8.2"
)

// NewMetricsCommand returns the `metrics` subcommand tree.
func NewMetricsCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "metrics",
		Short: "Manage and query node_exporter metrics on remote hosts",
		Long: `Install, manage, and query Prometheus node_exporter on remote hosts.

Examples:
  infractl metrics show web-01                       Display metrics summary
  infractl metrics top --all                         Multi-host vitals table
  infractl metrics query node_cpu web-01             Search metrics by pattern
  infractl metrics install --all                     Install node_exporter on all hosts
  infractl metrics service status web-01 db-01       Check service status`,
	}

	cmd.AddCommand(newMetricsShowCommand())
	cmd.AddCommand(newMetricsTopCommand())
	cmd.AddCommand(newMetricsQueryCommand())
	cmd.AddCommand(newMetricsInstallCommand())
	cmd.AddCommand(newMetricsServiceCommand())

	return cmd
}

// --- show ---

func newMetricsShowCommand() *cobra.Command {
	var port int
	cmd := &cobra.Command{
		Use:   "show <host>",
		Short: "Display a node_exporter metrics summary for a host",
		Long: `Fetch /metrics from node_exporter and display a human-readable summary:
load, CPU, memory, swap, filesystem usage, and network totals.`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			target, err := metricsTarget(args[0])
			if err != nil {
				return err
			}
			timeout := time.Duration(Global.Timeout) * time.Second
			samples, err := metrics.Fetch(target, port, timeout)
			if err != nil {
				return fmt.Errorf("fetch %s:%d: %w", target, port, err)
			}
			printMetricsShow(args[0], samples)
			return nil
		},
	}
	cmd.Flags().IntVar(&port, "port", defaultNEPort, "node_exporter port")
	return cmd
}

func printMetricsShow(hostname string, samples []metrics.Sample) {
	printHeader(fmt.Sprintf("node_exporter: %s", hostname))

	// Build info
	ver := metrics.LabelValue(samples, "node_exporter_build_info", "version")
	goVer := metrics.LabelValue(samples, "node_exporter_build_info", "goversion")
	if ver != "" {
		if goVer != "" {
			printKV("version", fmt.Sprintf("v%s (%s)", ver, goVer))
		} else {
			printKV("version", "v"+ver)
		}
	}

	// Kernel / uname
	release := metrics.LabelValue(samples, "node_uname_info", "release")
	machine := metrics.LabelValue(samples, "node_uname_info", "machine")
	if release != "" {
		printKV("kernel", fmt.Sprintf("Linux %s (%s)", release, machine))
	}

	// Uptime
	if boot, ok := metrics.FindFirst(samples, "node_boot_time_seconds"); ok {
		uptime := time.Since(time.Unix(int64(boot.Value), 0))
		printKV("uptime", formatUptime(uptime))
	}

	// Load averages
	fmt.Println()
	load1, _ := metrics.FindFirst(samples, "node_load1")
	load5, _ := metrics.FindFirst(samples, "node_load5")
	load15, _ := metrics.FindFirst(samples, "node_load15")
	printKV("LOAD", fmt.Sprintf("%.2f / %.2f / %.2f  (1m/5m/15m)",
		load1.Value, load5.Value, load15.Value))

	// CPU
	cpuPct, cores := computeCPU(samples)
	printKV("CPU", pctColor(cpuPct, 80, 90, fmt.Sprintf("%.1f%% used  (%d cores)", cpuPct, cores)))

	// Memory
	memUsed, memTotal, memPct := computeMem(samples)
	printKV("MEMORY", pctColor(memPct, 80, 90, fmt.Sprintf("%s / %s  (%.1f%%)",
		formatBytes(memUsed), formatBytes(memTotal), memPct)))

	// Swap
	swapTotal, _ := metrics.FindFirst(samples, "node_memory_SwapTotal_bytes")
	swapFree, _ := metrics.FindFirst(samples, "node_memory_SwapFree_bytes")
	if swapTotal.Value > 0 {
		swapUsed := swapTotal.Value - swapFree.Value
		swapPct := swapUsed / swapTotal.Value * 100
		printKV("SWAP", pctColor(swapPct, 50, 80, fmt.Sprintf("%s / %s  (%.1f%%)",
			formatBytes(swapUsed), formatBytes(swapTotal.Value), swapPct)))
	}

	// Filesystems
	fmt.Println()
	fmt.Printf("  \033[1m%-20s\033[0m\n", "FILESYSTEM")
	printFilesystems(samples)

	// Network
	fmt.Println()
	fmt.Printf("  \033[1m%-20s\033[0m %s\n", "NETWORK", "(cumulative bytes since boot)")
	printNetwork(samples)

	fmt.Println()
}

func printFilesystems(samples []metrics.Sample) {
	skipFSTypes := map[string]bool{
		"tmpfs": true, "devtmpfs": true, "sysfs": true, "proc": true,
		"cgroup": true, "cgroup2": true, "pstore": true, "securityfs": true,
		"debugfs": true, "tracefs": true, "configfs": true, "fusectl": true,
		"mqueue": true, "hugetlbfs": true, "rpc_pipefs": true, "nfsd": true,
		"overlay": true, "squashfs": true, "nsfs": true, "efivarfs": true,
	}

	type fsEntry struct {
		mountpoint string
		size       float64
		avail      float64
	}

	sizeMap := map[string]fsEntry{}
	for _, s := range metrics.FindAll(samples, "node_filesystem_size_bytes") {
		mp := s.Labels["mountpoint"]
		fstype := s.Labels["fstype"]
		if skipFSTypes[fstype] || mp == "" {
			continue
		}
		e := sizeMap[mp]
		e.mountpoint = mp
		e.size = s.Value
		sizeMap[mp] = e
	}
	for _, s := range metrics.FindAll(samples, "node_filesystem_avail_bytes") {
		mp := s.Labels["mountpoint"]
		if e, ok := sizeMap[mp]; ok {
			e.avail = s.Value
			sizeMap[mp] = e
		}
	}

	// Sort mountpoints: / first, then alphabetically
	mps := make([]string, 0, len(sizeMap))
	for mp := range sizeMap {
		mps = append(mps, mp)
	}
	sort.Slice(mps, func(i, j int) bool {
		if mps[i] == "/" {
			return true
		}
		if mps[j] == "/" {
			return false
		}
		return mps[i] < mps[j]
	})

	for _, mp := range mps {
		e := sizeMap[mp]
		if e.size == 0 {
			continue
		}
		used := e.size - e.avail
		pct := used / e.size * 100
		col := "green"
		if pct > 90 {
			col = "red"
		} else if pct > 75 {
			col = "yellow"
		}
		fmt.Printf("  %-24s %s / %s  (%s)\n",
			mp,
			formatBytes(used),
			formatBytes(e.size),
			colorize(col, fmt.Sprintf("%.1f%%", pct)),
		)
	}
}

func printNetwork(samples []metrics.Sample) {
	skipIfaces := map[string]bool{"lo": true}

	rxMap := map[string]float64{}
	txMap := map[string]float64{}

	for _, s := range metrics.FindAll(samples, "node_network_receive_bytes_total") {
		dev := s.Labels["device"]
		if !skipIfaces[dev] && !isVirtualIface(dev) {
			rxMap[dev] = s.Value
		}
	}
	for _, s := range metrics.FindAll(samples, "node_network_transmit_bytes_total") {
		dev := s.Labels["device"]
		if !skipIfaces[dev] && !isVirtualIface(dev) {
			txMap[dev] = s.Value
		}
	}

	devs := make([]string, 0, len(rxMap))
	for dev := range rxMap {
		devs = append(devs, dev)
	}
	sort.Strings(devs)

	for _, dev := range devs {
		fmt.Printf("  %-24s RX %-12s TX %s\n",
			dev, formatBytes(rxMap[dev]), formatBytes(txMap[dev]))
	}
}

func isVirtualIface(name string) bool {
	for _, prefix := range []string{"docker", "veth", "br-", "flannel", "cni", "tunl", "wg"} {
		if strings.HasPrefix(name, prefix) {
			return true
		}
	}
	return false
}

// --- top ---

func newMetricsTopCommand() *cobra.Command {
	var all bool
	var port int
	var sortBy string
	var warnCPU, warnMem, warnDisk float64

	cmd := &cobra.Command{
		Use:   "top [host...]",
		Short: "Show a node_exporter vitals table across multiple hosts",
		Long: `Fetch key metrics from node_exporter on one or more hosts and display
a compact table: load, CPU%, memory%, root disk%, and version.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			if !all && len(args) == 0 {
				return fmt.Errorf("specify host(s) or use --all")
			}
			hosts, err := resolveHostList(all, args)
			if err != nil {
				return err
			}
			return runMetricsTop(hosts, port, sortBy, warnCPU, warnMem, warnDisk)
		},
	}
	cmd.Flags().BoolVarP(&all, "all", "a", false, "Query all known hosts")
	cmd.Flags().IntVar(&port, "port", defaultNEPort, "node_exporter port")
	cmd.Flags().StringVar(&sortBy, "sort", "", "Sort by column: load, cpu, mem, disk")
	cmd.Flags().Float64Var(&warnCPU, "warn-cpu", 0, "Only show hosts with CPU% >= threshold")
	cmd.Flags().Float64Var(&warnMem, "warn-mem", 0, "Only show hosts with mem% >= threshold")
	cmd.Flags().Float64Var(&warnDisk, "warn-disk", 0, "Only show hosts with disk(/)% >= threshold")
	return cmd
}

type topResult struct {
	hostname string
	ok       bool
	err      string
	load1    float64
	cpuPct   float64
	memPct   float64
	diskPct  float64
	version  string
}

func runMetricsTop(hosts []*inventory.HostRecord, port int, sortBy string, warnCPU, warnMem, warnDisk float64) error {
	results := make([]topResult, len(hosts))
	var wg sync.WaitGroup
	sem := make(chan struct{}, 8)

	for i, h := range hosts {
		wg.Add(1)
		go func(idx int, hostname string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[idx] = fetchTop(hostname, port)
		}(i, h.Hostname)
	}
	wg.Wait()

	if sortBy != "" {
		sort.Slice(results, func(i, j int) bool {
			if !results[i].ok {
				return false
			}
			if !results[j].ok {
				return true
			}
			switch sortBy {
			case "load":
				return results[i].load1 > results[j].load1
			case "cpu":
				return results[i].cpuPct > results[j].cpuPct
			case "mem":
				return results[i].memPct > results[j].memPct
			case "disk":
				return results[i].diskPct > results[j].diskPct
			}
			return false
		})
	}

	if warnCPU > 0 || warnMem > 0 || warnDisk > 0 {
		filtered := results[:0]
		for _, r := range results {
			if !r.ok {
				continue
			}
			if (warnCPU > 0 && r.cpuPct >= warnCPU) ||
				(warnMem > 0 && r.memPct >= warnMem) ||
				(warnDisk > 0 && r.diskPct >= warnDisk) {
				filtered = append(filtered, r)
			}
		}
		results = filtered
	}

	fmt.Printf("\n%-24s %-8s %-7s %-7s %-9s %s\n",
		"HOST", "LOAD1", "CPU%", "MEM%", "DISK(/)", "VERSION")
	fmt.Println(strings.Repeat("─", 70))

	for _, r := range results {
		if !r.ok {
			fmt.Printf("%-24s %s\n", r.hostname,
				colorize("red", "FAIL  "+r.err))
			continue
		}
		fmt.Printf("%-24s %-8.2f %-7s %-7s %-9s %s\n",
			r.hostname,
			r.load1,
			pctColor(r.cpuPct, 80, 90, fmt.Sprintf("%.1f%%", r.cpuPct)),
			pctColor(r.memPct, 80, 90, fmt.Sprintf("%.1f%%", r.memPct)),
			pctColor(r.diskPct, 75, 90, fmt.Sprintf("%.1f%%", r.diskPct)),
			"v"+r.version,
		)
	}
	fmt.Println()
	return nil
}

func fetchTop(hostname string, port int) topResult {
	r := topResult{hostname: hostname}
	target, err := metricsTarget(hostname)
	if err != nil {
		r.err = err.Error()
		return r
	}
	timeout := time.Duration(Global.Timeout) * time.Second
	samples, err := metrics.Fetch(target, port, timeout)
	if err != nil {
		r.err = err.Error()
		return r
	}
	r.ok = true
	r.load1, _ = func() (float64, bool) {
		s, ok := metrics.FindFirst(samples, "node_load1")
		return s.Value, ok
	}()
	r.cpuPct, _ = computeCPU(samples)
	_, _, r.memPct = computeMem(samples)
	_, _, r.diskPct = computeRootDisk(samples)
	r.version = metrics.LabelValue(samples, "node_exporter_build_info", "version")
	return r
}

// --- query ---

func newMetricsQueryCommand() *cobra.Command {
	var all bool
	var port int

	cmd := &cobra.Command{
		Use:   "query <pattern> [host...]",
		Short: "Search node_exporter metrics by name pattern",
		Long: `Fetch /metrics from node_exporter and filter by name pattern.
Pattern is a substring match unless it contains '*' (glob).

Examples:
  infractl metrics query node_cpu web-01
  infractl metrics query 'node_memory_*_bytes' web-01 db-01
  infractl metrics query node_disk --all`,
		Args: cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			pattern := args[0]
			hostArgs := args[1:]
			if !all && len(hostArgs) == 0 {
				return fmt.Errorf("specify host(s) or use --all")
			}
			hosts, err := resolveHostList(all, hostArgs)
			if err != nil {
				return err
			}
			return runMetricsQuery(pattern, hosts, port)
		},
	}
	cmd.Flags().BoolVarP(&all, "all", "a", false, "Query all known hosts")
	cmd.Flags().IntVar(&port, "port", defaultNEPort, "node_exporter port")
	return cmd
}

type queryResult struct {
	hostname string
	err      string
	matched  []metrics.Sample
}

func fetchQueryResult(hostname string, port int, pattern string) queryResult {
	r := queryResult{hostname: hostname}
	target, err := metricsTarget(hostname)
	if err != nil {
		r.err = err.Error()
		return r
	}
	timeout := time.Duration(Global.Timeout) * time.Second
	samples, err := metrics.Fetch(target, port, timeout)
	if err != nil {
		r.err = err.Error()
		return r
	}
	r.matched = metrics.Filter(samples, pattern)
	return r
}

func runMetricsQuery(pattern string, hosts []*inventory.HostRecord, port int) error {
	results := make([]queryResult, len(hosts))
	var wg sync.WaitGroup
	sem := make(chan struct{}, 8)

	for i, h := range hosts {
		wg.Add(1)
		go func(idx int, hostname string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[idx] = fetchQueryResult(hostname, port, pattern)
		}(i, h.Hostname)
	}
	wg.Wait()

	for _, r := range results {
		if r.err != "" {
			fmt.Printf("%s: %s\n", r.hostname, colorize("red", r.err))
			continue
		}
		if len(r.matched) == 0 {
			fmt.Printf("%s: no metrics match %q\n", r.hostname, pattern)
			continue
		}
		if len(hosts) > 1 {
			printHeader(r.hostname)
		}
		fmt.Printf("\n%-50s %-40s %s\n", "METRIC", "LABELS", "VALUE")
		fmt.Println(strings.Repeat("─", 100))
		for _, s := range r.matched {
			labelStr := metrics.FormatLabels(s.Labels)
			var valStr string
			if s.Value == math.Trunc(s.Value) && math.Abs(s.Value) < 1e15 {
				valStr = fmt.Sprintf("%d", int64(s.Value))
			} else {
				valStr = fmt.Sprintf("%g", s.Value)
			}
			fmt.Printf("%-50s %-40s %s\n", s.Name, labelStr, valStr)
		}
		fmt.Printf("\n%d metric(s) matched\n\n", len(r.matched))
	}
	return nil
}

// --- install ---

func newMetricsInstallCommand() *cobra.Command {
	var all bool
	var version string

	cmd := &cobra.Command{
		Use:   "install [host...]",
		Short: "Install node_exporter on remote hosts via SSH",
		Long: `Download and install Prometheus node_exporter on one or more remote hosts.
Requires root/sudo access over SSH. Creates a systemd service and starts it.

Examples:
  infractl metrics install web-01
  infractl metrics install --all
  infractl metrics install --version 1.8.2 web-01 db-01`,
		RunE: func(cmd *cobra.Command, args []string) error {
			if !all && len(args) == 0 {
				return fmt.Errorf("specify host(s) or use --all")
			}
			hosts, err := resolveHostList(all, args)
			if err != nil {
				return err
			}
			return runMetricsInstall(hosts, version)
		},
	}
	cmd.Flags().BoolVarP(&all, "all", "a", false, "Install on all known hosts")
	cmd.Flags().StringVar(&version, "version", defaultNEVersion, "node_exporter version to install")
	return cmd
}

// nodeExporterUnit is the systemd service unit for node_exporter.
var nodeExporterUnit = `[Unit]
Description=Prometheus Node Exporter
Documentation=https://prometheus.io/docs/guides/node-exporter/
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter
SyslogIdentifier=node_exporter
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
`

func buildInstallScript(version string) string {
	unitB64 := base64.StdEncoding.EncodeToString([]byte(nodeExporterUnit))
	return fmt.Sprintf(`set -e
VERSION=%s
TARBALL=node_exporter-${VERSION}.linux-amd64.tar.gz
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Skip if already at desired version
if [ -x /usr/local/bin/node_exporter ]; then
    INSTALLED=$(/usr/local/bin/node_exporter --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
    if [ "$INSTALLED" = "$VERSION" ]; then
        echo "STATUS=already_installed"
        echo "VERSION=$VERSION"
        exit 0
    fi
    echo "UPGRADE_FROM=$INSTALLED"
fi

# Download
URL="https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/${TARBALL}"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$TMPDIR/$TARBALL" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$TMPDIR/$TARBALL" "$URL"
else
    echo "STATUS=error:no_downloader"
    exit 1
fi

tar xzf "$TMPDIR/$TARBALL" -C "$TMPDIR"
cp "$TMPDIR/node_exporter-${VERSION}.linux-amd64/node_exporter" /usr/local/bin/node_exporter
chmod 755 /usr/local/bin/node_exporter

# Create system user
id node_exporter >/dev/null 2>&1 || useradd -r -s /sbin/nologin -d /nonexistent -c "Prometheus Node Exporter" node_exporter

# Write systemd unit (base64-encoded to avoid quoting issues)
echo '%s' | base64 -d > /etc/systemd/system/node_exporter.service

systemctl daemon-reload
systemctl enable node_exporter
systemctl restart node_exporter
STATUS=$(systemctl is-active node_exporter 2>/dev/null || echo "failed")
echo "STATUS=$STATUS"
echo "VERSION=$VERSION"
`, version, unitB64)
}

type installResult struct {
	hostname    string
	execErr     string
	scriptErr   string
	status      string
	installedVer string
	upgradeFrom string
}

func doInstall(hostname, version string) installResult {
	r := installResult{hostname: hostname}
	ex, err := executorFor(hostname)
	if err != nil {
		r.execErr = err.Error()
		return r
	}
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	out, err := ex.Run(ctx, buildInstallScript(version))
	cancel()
	if err != nil {
		r.scriptErr = strings.TrimSpace(err.Error())
		return r
	}
	info := parseKV(out)
	r.status = info["STATUS"]
	r.installedVer = info["VERSION"]
	r.upgradeFrom = info["UPGRADE_FROM"]
	return r
}

func runMetricsInstall(hosts []*inventory.HostRecord, version string) error {
	results := make([]installResult, len(hosts))
	var wg sync.WaitGroup
	sem := make(chan struct{}, 4)

	for i, h := range hosts {
		wg.Add(1)
		go func(idx int, hostname string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[idx] = doInstall(hostname, version)
		}(i, h.Hostname)
	}
	wg.Wait()

	for _, r := range results {
		fmt.Printf("%s:\n", colorize("bold", r.hostname))
		switch {
		case r.execErr != "":
			fmt.Printf("  %s\n\n", colorize("red", r.execErr))
		case r.scriptErr != "":
			fmt.Printf("  %s: %s\n\n", colorize("red", "FAIL"), r.scriptErr)
		case r.status == "already_installed":
			fmt.Printf("  already at v%s — nothing to do\n\n", r.installedVer)
		case r.status == "active":
			if r.upgradeFrom != "" {
				fmt.Printf("  upgraded v%s → v%s\n", r.upgradeFrom, r.installedVer)
			} else {
				fmt.Printf("  installed v%s\n", r.installedVer)
			}
			fmt.Printf("  service: %s\n\n", colorize("green", "active (running)"))
		default:
			fmt.Printf("  %s  status=%s\n\n", colorize("yellow", "WARNING"), r.status)
		}
	}
	return nil
}

// --- service ---

func newMetricsServiceCommand() *cobra.Command {
	var all bool

	cmd := &cobra.Command{
		Use:   "service <start|stop|restart|status> [host...]",
		Short: "Manage the node_exporter systemd service on remote hosts",
		Long: `Run a systemctl action against the node_exporter service.

Examples:
  infractl metrics service status web-01
  infractl metrics service restart --all
  infractl metrics service stop db-01 cache-01`,
		Args: cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			action := args[0]
			validActions := map[string]bool{"start": true, "stop": true, "restart": true, "status": true}
			if !validActions[action] {
				return fmt.Errorf("unknown action %q — must be start, stop, restart, or status", action)
			}
			hostArgs := args[1:]
			if !all && len(hostArgs) == 0 {
				return fmt.Errorf("specify host(s) or use --all")
			}
			hosts, err := resolveHostList(all, hostArgs)
			if err != nil {
				return err
			}
			return runMetricsService(action, hosts)
		},
	}
	cmd.Flags().BoolVarP(&all, "all", "a", false, "Apply to all known hosts")
	return cmd
}

func runMetricsService(action string, hosts []*inventory.HostRecord) error {
	for _, h := range hosts {
		ex, err := executorFor(h.Hostname)
		if err != nil {
			fmt.Printf("%s: %s\n", h.Hostname, colorize("red", err.Error()))
			continue
		}

		ctx, cancel := context.WithTimeout(context.Background(),
			time.Duration(Global.Timeout)*time.Second)
		script := fmt.Sprintf("systemctl %s node_exporter 2>&1", action)
		out, err := ex.Run(ctx, script)
		cancel()

		out = strings.TrimSpace(out)
		if err != nil {
			fmt.Printf("%s: %s\n  %s\n", h.Hostname, colorize("red", "FAIL"), out)
		} else if action == "status" {
			fmt.Printf("%s:\n%s\n", colorize("bold", h.Hostname), indent(out, "  "))
		} else {
			fmt.Printf("%s: %s\n", h.Hostname, colorize("green", action+" OK"))
		}
	}
	return nil
}

// --- helpers ---

// metricsTarget resolves a hostname to an HTTP-reachable address (IP or hostname).
func metricsTarget(hostname string) (string, error) {
	h, err := resolveHost(hostname)
	if err != nil {
		return hostname, nil
	}
	target := h.Target
	// Strip user@ prefix if somehow present
	if at := strings.LastIndex(target, "@"); at >= 0 {
		target = target[at+1:]
	}
	if target == "" {
		return hostname, nil
	}
	return target, nil
}

// resolveHostList builds a host slice from --all or explicit names.
func resolveHostList(all bool, names []string) ([]*inventory.HostRecord, error) {
	if all {
		return allHosts()
	}
	hosts := make([]*inventory.HostRecord, len(names))
	for i, name := range names {
		hosts[i] = &inventory.HostRecord{Hostname: name}
	}
	return hosts, nil
}

// computeCPU returns CPU usage percent and core count from node_cpu_seconds_total samples.
// Uses lifetime totals (ratio of non-idle time), not an instantaneous rate.
func computeCPU(samples []metrics.Sample) (pct float64, cores int) {
	var total, idle float64
	coreSet := map[string]bool{}
	for _, s := range metrics.FindAll(samples, "node_cpu_seconds_total") {
		total += s.Value
		if s.Labels["mode"] == "idle" {
			idle += s.Value
		}
		if cpu := s.Labels["cpu"]; cpu != "" {
			coreSet[cpu] = true
		}
	}
	cores = len(coreSet)
	if total > 0 {
		pct = (total - idle) / total * 100
	}
	return
}

// computeMem returns (used, total, pct) from node_memory samples.
func computeMem(samples []metrics.Sample) (used, total, pct float64) {
	t, ok := metrics.FindFirst(samples, "node_memory_MemTotal_bytes")
	if !ok {
		return
	}
	a, ok := metrics.FindFirst(samples, "node_memory_MemAvailable_bytes")
	if !ok {
		return
	}
	total = t.Value
	used = total - a.Value
	if total > 0 {
		pct = used / total * 100
	}
	return
}

// computeRootDisk returns (used, total, pct) for the root filesystem.
func computeRootDisk(samples []metrics.Sample) (used, total, pct float64) {
	for _, s := range metrics.FindAll(samples, "node_filesystem_size_bytes") {
		if s.Labels["mountpoint"] == "/" {
			total = s.Value
			break
		}
	}
	for _, s := range metrics.FindAll(samples, "node_filesystem_avail_bytes") {
		if s.Labels["mountpoint"] == "/" {
			avail := s.Value
			used = total - avail
			if total > 0 {
				pct = used / total * 100
			}
			break
		}
	}
	return
}

// formatBytes returns a human-readable byte count (B, KiB, MiB, GiB, TiB).
func formatBytes(b float64) string {
	const unit = 1024.0
	if b < unit {
		return fmt.Sprintf("%.0f B", b)
	}
	div := unit
	for _, suffix := range []string{"KiB", "MiB", "GiB", "TiB", "PiB"} {
		if b < div*unit {
			return fmt.Sprintf("%.1f %s", b/div, suffix)
		}
		div *= unit
	}
	return fmt.Sprintf("%.1f EiB", b/div)
}

// pctColor returns text colorized green/yellow/red based on percentage thresholds.
func pctColor(pct, warn, crit float64, text string) string {
	if pct > crit {
		return colorize("red", text)
	}
	if pct > warn {
		return colorize("yellow", text)
	}
	return colorize("green", text)
}

// formatUptime formats a duration as "Xd Xh Xm".
func formatUptime(d time.Duration) string {
	d = d.Truncate(time.Minute)
	days := int(d.Hours()) / 24
	hours := int(d.Hours()) % 24
	mins := int(d.Minutes()) % 60
	if days > 0 {
		return fmt.Sprintf("%dd %dh %dm", days, hours, mins)
	}
	if hours > 0 {
		return fmt.Sprintf("%dh %dm", hours, mins)
	}
	return fmt.Sprintf("%dm", mins)
}

// parseKV extracts KEY=VALUE pairs from multi-line script output.
func parseKV(out string) map[string]string {
	m := map[string]string{}
	for _, line := range strings.Split(out, "\n") {
		kv := strings.SplitN(strings.TrimSpace(line), "=", 2)
		if len(kv) == 2 {
			m[kv[0]] = kv[1]
		}
	}
	return m
}

// indent prefixes each line of s with prefix.
func indent(s, prefix string) string {
	lines := strings.Split(s, "\n")
	for i, l := range lines {
		if l != "" {
			lines[i] = prefix + l
		}
	}
	return strings.Join(lines, "\n")
}
