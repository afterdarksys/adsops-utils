// Package metrics provides a Prometheus text format parser and HTTP fetcher
// for querying node_exporter /metrics endpoints.
package metrics

import (
	"bufio"
	"fmt"
	"io"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// Sample is a single metric observation from Prometheus text format.
type Sample struct {
	Name   string
	Labels map[string]string
	Value  float64
}

// Fetch retrieves Prometheus metrics from a node_exporter /metrics endpoint.
func Fetch(host string, port int, timeout time.Duration) ([]Sample, error) {
	url := fmt.Sprintf("http://%s:%d/metrics", host, port)
	client := &http.Client{Timeout: timeout}
	resp, err := client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d from %s", resp.StatusCode, url)
	}
	return Parse(resp.Body)
}

// Parse reads Prometheus text exposition format from r and returns all valid samples.
// Lines starting with # (HELP/TYPE comments) and blank lines are skipped.
// NaN and ±Inf values are dropped.
func Parse(r io.Reader) ([]Sample, error) {
	var samples []Sample
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 1<<20), 1<<20) // 1 MiB per line — node_exporter safe
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		s, err := parseSample(line)
		if err != nil {
			continue
		}
		if math.IsNaN(s.Value) || math.IsInf(s.Value, 0) {
			continue
		}
		samples = append(samples, s)
	}
	return samples, scanner.Err()
}

// Filter returns samples whose name contains pattern as a substring, or
// glob-matches it when pattern contains '*'.
func Filter(samples []Sample, pattern string) []Sample {
	if pattern == "" {
		return samples
	}
	var out []Sample
	for _, s := range samples {
		if matchPattern(pattern, s.Name) {
			out = append(out, s)
		}
	}
	return out
}

// FindFirst returns the first sample with exactly the given name.
func FindFirst(samples []Sample, name string) (Sample, bool) {
	for _, s := range samples {
		if s.Name == name {
			return s, true
		}
	}
	return Sample{}, false
}

// FindAll returns all samples with exactly the given name.
func FindAll(samples []Sample, name string) []Sample {
	var out []Sample
	for _, s := range samples {
		if s.Name == name {
			out = append(out, s)
		}
	}
	return out
}

// Sum returns the sum of all sample values with exactly the given name.
func Sum(samples []Sample, name string) float64 {
	var total float64
	for _, s := range samples {
		if s.Name == name {
			total += s.Value
		}
	}
	return total
}

// LabelValue returns the value of labelKey from the first sample matching name.
func LabelValue(samples []Sample, name, labelKey string) string {
	for _, s := range samples {
		if s.Name == name {
			return s.Labels[labelKey]
		}
	}
	return ""
}

// FormatLabels returns a Prometheus-style label string, e.g. {cpu="0",mode="idle"}.
// Returns "" when there are no labels.
func FormatLabels(labels map[string]string) string {
	if len(labels) == 0 {
		return ""
	}
	keys := make([]string, 0, len(labels))
	for k := range labels {
		keys = append(keys, k)
	}
	// Sort for deterministic output
	for i := 1; i < len(keys); i++ {
		for j := i; j > 0 && keys[j] < keys[j-1]; j-- {
			keys[j], keys[j-1] = keys[j-1], keys[j]
		}
	}
	parts := make([]string, len(keys))
	for i, k := range keys {
		parts[i] = fmt.Sprintf(`%s="%s"`, k, labels[k])
	}
	return "{" + strings.Join(parts, ",") + "}"
}

// --- parsing helpers ---

func parseSample(line string) (Sample, error) {
	nameEnd := strings.IndexAny(line, "{ ")
	if nameEnd < 0 {
		// No labels, no space found: malformed
		return Sample{}, fmt.Errorf("no separator in %q", line)
	}

	name := line[:nameEnd]
	rest := line[nameEnd:]

	labels := map[string]string{}
	if strings.HasPrefix(rest, "{") {
		end := strings.Index(rest, "}")
		if end < 0 {
			return Sample{}, fmt.Errorf("unclosed label set")
		}
		labels = parseLabels(rest[1:end])
		rest = strings.TrimSpace(rest[end+1:])
	} else {
		rest = strings.TrimSpace(rest)
	}

	fields := strings.Fields(rest)
	if len(fields) == 0 {
		return Sample{}, fmt.Errorf("missing value")
	}
	v, err := parseValue(fields[0])
	if err != nil {
		return Sample{}, err
	}
	return Sample{Name: name, Labels: labels, Value: v}, nil
}

// parseLabels parses the interior of a label set, e.g. key="val",key2="val2".
func parseLabels(s string) map[string]string {
	m := map[string]string{}
	for s != "" {
		s = strings.TrimSpace(s)
		eq := strings.Index(s, `="`)
		if eq < 0 {
			break
		}
		key := strings.TrimSpace(s[:eq])
		s = s[eq+2:] // skip key="
		var val strings.Builder
		i := 0
		for i < len(s) {
			c := s[i]
			if c == '\\' && i+1 < len(s) {
				i++
				switch s[i] {
				case 'n':
					val.WriteByte('\n')
				case '\\':
					val.WriteByte('\\')
				case '"':
					val.WriteByte('"')
				default:
					val.WriteByte(s[i])
				}
			} else if c == '"' {
				s = s[i+1:]
				break
			} else {
				val.WriteByte(c)
			}
			i++
		}
		m[key] = val.String()
		s = strings.TrimPrefix(s, ",")
	}
	return m
}

func parseValue(s string) (float64, error) {
	switch s {
	case "+Inf":
		return math.Inf(1), nil
	case "-Inf":
		return math.Inf(-1), nil
	case "NaN":
		return math.NaN(), nil
	}
	return strconv.ParseFloat(s, 64)
}

// matchPattern returns true if name matches pattern.
// If pattern contains no '*', it is a substring match.
// Otherwise it is a simple glob (only '*' wildcard supported).
func matchPattern(pattern, name string) bool {
	if !strings.Contains(pattern, "*") {
		return strings.Contains(name, pattern)
	}
	return globMatch(pattern, name)
}

func globMatch(pattern, name string) bool {
	if pattern == "" {
		return name == ""
	}
	if pattern == "*" {
		return true
	}
	if pattern[0] == '*' {
		for i := 0; i <= len(name); i++ {
			if globMatch(pattern[1:], name[i:]) {
				return true
			}
		}
		return false
	}
	if name == "" || pattern[0] != name[0] {
		return false
	}
	return globMatch(pattern[1:], name[1:])
}
