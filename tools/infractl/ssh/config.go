package ssh

import (
	"bufio"
	"os"
	"path/filepath"
	"strings"
)

// ConfigEntry represents a parsed Host block from ~/.ssh/config.
type ConfigEntry struct {
	Name         string
	HostName     string
	User         string
	Port         string
	IdentityFile string
}

// ParseConfig reads the SSH config file and returns all non-wildcard entries.
func ParseConfig(configPath string) ([]ConfigEntry, error) {
	if configPath == "" {
		home, _ := os.UserHomeDir()
		configPath = filepath.Join(home, ".ssh", "config")
	}
	return parseFile(configPath, map[string]bool{})
}

// LookupHost returns the SSH config entry for a given host alias.
// Falls back to a Host struct with Name==alias as the target if not found.
func LookupHost(alias string) Host {
	home, _ := os.UserHomeDir()
	entries, err := parseFile(filepath.Join(home, ".ssh", "config"), map[string]bool{})
	if err != nil {
		return Host{Name: alias, Target: alias}
	}
	for _, e := range entries {
		if e.Name == alias {
			target := e.HostName
			if target == "" {
				target = alias
			}
			return Host{
				Name:         alias,
				Target:       target,
				User:         e.User,
				Port:         e.Port,
				IdentityFile: e.IdentityFile,
			}
		}
	}
	// Not in config — use the alias directly as the hostname
	return Host{Name: alias, Target: alias}
}

func parseFile(path string, seen map[string]bool) ([]ConfigEntry, error) {
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

	var entries []ConfigEntry
	var cur *ConfigEntry

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

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
			if !filepath.IsAbs(value) {
				home, _ := os.UserHomeDir()
				value = filepath.Join(home, ".ssh", value)
			}
			matches, _ := filepath.Glob(value)
			for _, m := range matches {
				sub, _ := parseFile(m, seen)
				entries = append(entries, sub...)
			}
		case "host":
			if cur != nil && !isWildcard(cur.Name) {
				entries = append(entries, *cur)
			}
			if !isWildcard(value) {
				cur = &ConfigEntry{Name: value}
			} else {
				cur = nil
			}
		case "hostname":
			if cur != nil {
				cur.HostName = value
			}
		case "user":
			if cur != nil {
				cur.User = value
			}
		case "port":
			if cur != nil {
				cur.Port = value
			}
		case "identityfile":
			if cur != nil {
				if strings.HasPrefix(value, "~/") {
					home, _ := os.UserHomeDir()
					value = filepath.Join(home, value[2:])
				}
				cur.IdentityFile = value
			}
		}
	}
	if cur != nil && !isWildcard(cur.Name) {
		entries = append(entries, *cur)
	}
	return entries, scanner.Err()
}

func isWildcard(name string) bool {
	return strings.ContainsAny(name, "*?!")
}
