// Package ssh provides an SSH executor that runs commands on remote hosts.
// It delegates to the system's ssh binary, respecting ~/.ssh/config fully.
package ssh

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"time"
)

// Host describes a remote host's SSH connection parameters.
type Host struct {
	// Name is the inventory name / SSH alias
	Name string
	// Target is the SSH destination: [user@]hostname[:port]
	Target string
	// IdentityFile is an optional path to a private key
	IdentityFile string
	// Port overrides the default SSH port
	Port string
	// User overrides the SSH user
	User string
}

// Executor runs commands on a remote host over SSH.
type Executor struct {
	host    Host
	timeout time.Duration
	verbose bool
}

// NewExecutor creates an Executor for the given host.
func NewExecutor(h Host, timeout time.Duration, verbose bool) *Executor {
	return &Executor{host: h, timeout: timeout, verbose: verbose}
}

// Run executes cmd on the remote host and returns combined stdout+stderr.
func (e *Executor) Run(ctx context.Context, cmd string) (string, error) {
	args := e.buildSSHArgs()
	args = append(args, cmd)

	if ctx == nil {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(context.Background(), e.timeout)
		defer cancel()
	}

	c := exec.CommandContext(ctx, "ssh", args...)
	out, err := c.CombinedOutput()
	if e.verbose {
		fmt.Fprintf(os.Stderr, "[ssh %s] %s\n", e.host.Name, cmd)
	}
	return string(out), err
}

// RunSplit runs cmd and returns stdout and stderr separately.
func (e *Executor) RunSplit(ctx context.Context, cmd string) (stdout, stderr string, err error) {
	args := e.buildSSHArgs()
	args = append(args, cmd)

	if ctx == nil {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(context.Background(), e.timeout)
		defer cancel()
	}

	var stdoutBuf, stderrBuf bytes.Buffer
	c := exec.CommandContext(ctx, "ssh", args...)
	c.Stdout = &stdoutBuf
	c.Stderr = &stderrBuf

	err = c.Run()
	return stdoutBuf.String(), stderrBuf.String(), err
}

// Stream runs cmd and streams stdout/stderr directly to the provided writers.
// Used for `logs -f`, `exec`, etc.
func (e *Executor) Stream(ctx context.Context, cmd string, stdout, stderr io.Writer) error {
	args := e.buildSSHArgs()
	args = append(args, cmd)

	c := exec.CommandContext(ctx, "ssh", args...)
	c.Stdout = stdout
	c.Stderr = stderr
	c.Stdin = os.Stdin
	return c.Run()
}

// ScpTo copies a local file to the remote host.
func (e *Executor) ScpTo(ctx context.Context, localPath, remotePath string) error {
	args := e.buildScpArgs()
	args = append(args, localPath)
	args = append(args, fmt.Sprintf("%s:%s", e.host.Target, remotePath))

	c := exec.CommandContext(ctx, "scp", args...)
	c.Stdout = os.Stdout
	c.Stderr = os.Stderr
	return c.Run()
}

// ScpFrom copies a file from the remote host to local.
func (e *Executor) ScpFrom(ctx context.Context, remotePath, localPath string) error {
	args := e.buildScpArgs()
	args = append(args, fmt.Sprintf("%s:%s", e.host.Target, remotePath))
	args = append(args, localPath)

	c := exec.CommandContext(ctx, "scp", args...)
	c.Stdout = os.Stdout
	c.Stderr = os.Stderr
	return c.Run()
}

func (e *Executor) buildSSHArgs() []string {
	args := []string{
		"-o", "StrictHostKeyChecking=accept-new",
		"-o", fmt.Sprintf("ConnectTimeout=%d", int(e.timeout.Seconds())),
		"-o", "BatchMode=yes",
	}
	if e.host.Port != "" && e.host.Port != "22" {
		args = append(args, "-p", e.host.Port)
	}
	if e.host.IdentityFile != "" {
		args = append(args, "-i", e.host.IdentityFile)
	}
	target := e.host.Target
	if e.host.User != "" && !strings.Contains(target, "@") {
		target = e.host.User + "@" + target
	}
	args = append(args, target)
	return args
}

func (e *Executor) buildScpArgs() []string {
	args := []string{
		"-o", "StrictHostKeyChecking=accept-new",
		"-o", fmt.Sprintf("ConnectTimeout=%d", int(e.timeout.Seconds())),
		"-o", "BatchMode=yes",
	}
	if e.host.Port != "" && e.host.Port != "22" {
		args = append(args, "-P", e.host.Port)
	}
	if e.host.IdentityFile != "" {
		args = append(args, "-i", e.host.IdentityFile)
	}
	return args
}

// HostName returns the display name for the host.
func (e *Executor) HostName() string {
	return e.host.Name
}
