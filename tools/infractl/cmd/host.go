// Package cmd contains all CLI subcommands for infractl.
package cmd

import (
	"fmt"
	"os"
	"time"

	"github.com/afterdarksys/adsops-utils/tools/infractl/inventory"
	"github.com/afterdarksys/adsops-utils/tools/infractl/ssh"
)

// GlobalFlags holds flags shared by all subcommands.
type GlobalFlags struct {
	Timeout int
	Verbose bool
}

// Global is the shared flags instance, populated by the root command.
var Global = &GlobalFlags{Timeout: 15}

// resolveHost returns an ssh.Host for the given name (inventory → ssh config → direct).
func resolveHost(name string) (ssh.Host, error) {
	rec, err := inventory.GetHost(name)
	if err != nil {
		// Last resort: use the name directly as the SSH target
		return ssh.Host{Name: name, Target: name}, nil
	}

	target := rec.IP
	if target == "" {
		target = name
	}
	return ssh.Host{
		Name:         rec.Hostname,
		Target:       target,
		User:         rec.SSHUser,
		Port:         rec.SSHPort,
		IdentityFile: rec.SSHKey,
	}, nil
}

// executorFor returns an SSH executor for the named host.
func executorFor(hostname string) (*ssh.Executor, error) {
	h, err := resolveHost(hostname)
	if err != nil {
		return nil, err
	}
	timeout := time.Duration(Global.Timeout) * time.Second
	return ssh.NewExecutor(h, timeout, Global.Verbose), nil
}

// allHosts returns every host from the inventory / ssh config.
func allHosts() ([]*inventory.HostRecord, error) {
	return inventory.ListHosts()
}

// printHeader prints a formatted section header.
func printHeader(title string) {
	fmt.Printf("\n\033[1;36m── %s \033[0m\n", title)
}

// printKV prints a key-value pair.
func printKV(key, value string) {
	fmt.Printf("  \033[1m%-20s\033[0m %s\n", key+":", value)
}

// colorize wraps text in an ANSI color escape.
func colorize(color, text string) string {
	codes := map[string]string{
		"red":    "\033[31m",
		"green":  "\033[32m",
		"yellow": "\033[33m",
		"blue":   "\033[34m",
		"cyan":   "\033[36m",
		"bold":   "\033[1m",
		"reset":  "\033[0m",
	}
	return codes[color] + text + codes["reset"]
}

// errorf prints an error to stderr and exits 1.
func fatalf(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, colorize("red", "error")+": "+format+"\n", args...)
	os.Exit(1)
}
