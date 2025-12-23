package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Config represents the root cloudtop configuration
type Config struct {
	Version   string              `json:"version"`
	Providers map[string]Provider `json:"providers"`
	Defaults  Defaults            `json:"defaults"`
	Output    OutputConfig        `json:"output"`
	Cache     CacheConfig         `json:"cache"`
}

// Provider represents a single provider configuration
type Provider struct {
	Enabled   bool                   `json:"enabled"`
	Auth      AuthConfig             `json:"auth"`
	Regions   []string               `json:"regions,omitempty"`
	Services  []string               `json:"services,omitempty"`
	RateLimit *RateLimitConfig       `json:"rate_limit,omitempty"`
	Timeout   Duration               `json:"timeout,omitempty"`
	Options   map[string]interface{} `json:"options,omitempty"`
}

// AuthConfig handles multiple authentication methods
type AuthConfig struct {
	Method       string `json:"method"` // "api_key", "oauth", "service_account", "env"
	APIKey       string `json:"api_key,omitempty"`
	APISecret    string `json:"api_secret,omitempty"`
	ClientID     string `json:"client_id,omitempty"`
	ClientSecret string `json:"client_secret,omitempty"`
	TokenURL     string `json:"token_url,omitempty"`
	KeyFile      string `json:"key_file,omitempty"`
	EnvAPIKey    string `json:"env_api_key,omitempty"`
	EnvSecret    string `json:"env_secret,omitempty"`
}

// ToCredentials converts AuthConfig to a credentials map
func (a *AuthConfig) ToCredentials() map[string]string {
	creds := make(map[string]string)

	switch a.Method {
	case "api_key":
		if a.EnvAPIKey != "" {
			creds["api_token"] = os.Getenv(a.EnvAPIKey)
		} else if a.APIKey != "" {
			creds["api_token"] = a.APIKey
		}
		if a.EnvSecret != "" {
			creds["api_secret"] = os.Getenv(a.EnvSecret)
		} else if a.APISecret != "" {
			creds["api_secret"] = a.APISecret
		}
	case "service_account":
		if a.KeyFile != "" {
			// Expand ~ to home directory
			if a.KeyFile[0] == '~' {
				home, _ := os.UserHomeDir()
				creds["key_file"] = filepath.Join(home, a.KeyFile[1:])
			} else {
				creds["key_file"] = a.KeyFile
			}
		}
	case "oauth":
		creds["client_id"] = a.ClientID
		creds["client_secret"] = a.ClientSecret
		creds["token_url"] = a.TokenURL
	case "env":
		if a.EnvAPIKey != "" {
			creds["api_token"] = os.Getenv(a.EnvAPIKey)
		}
		if a.EnvSecret != "" {
			creds["api_secret"] = os.Getenv(a.EnvSecret)
		}
	}

	return creds
}

// RateLimitConfig defines rate limiting parameters
type RateLimitConfig struct {
	RequestsPerSecond float64  `json:"requests_per_second"`
	Burst             int      `json:"burst"`
	Timeout           Duration `json:"timeout"`
}

// Defaults for CLI behavior
type Defaults struct {
	RefreshInterval Duration `json:"refresh_interval"`
	OutputFormat    string   `json:"output_format"` // "table", "wide", "json"
	ShowCached      bool     `json:"show_cached"`
}

// OutputConfig controls output formatting
type OutputConfig struct {
	ColorEnabled bool                `json:"color_enabled"`
	Timestamps   bool                `json:"timestamps"`
	Columns      map[string][]string `json:"columns,omitempty"`
}

// CacheConfig for cache settings
type CacheConfig struct {
	Enabled  bool     `json:"enabled"`
	Backend  string   `json:"backend"` // "memory", "redis", "file"
	TTL      Duration `json:"ttl"`
	MaxSize  int      `json:"max_size"`
	RedisURL string   `json:"redis_url,omitempty"`
	CacheDir string   `json:"cache_dir,omitempty"`
}

// Duration is a wrapper for time.Duration that supports JSON
type Duration time.Duration

func (d Duration) Duration() time.Duration {
	return time.Duration(d)
}

func (d *Duration) UnmarshalJSON(b []byte) error {
	var v interface{}
	if err := json.Unmarshal(b, &v); err != nil {
		return err
	}
	switch value := v.(type) {
	case float64:
		*d = Duration(time.Duration(value))
	case string:
		dur, err := time.ParseDuration(value)
		if err != nil {
			return err
		}
		*d = Duration(dur)
	default:
		return fmt.Errorf("invalid duration type: %T", v)
	}
	return nil
}

func (d Duration) MarshalJSON() ([]byte, error) {
	return json.Marshal(time.Duration(d).String())
}

// Load loads configuration from a file
func Load(path string) (*Config, error) {
	if path == "" {
		return DefaultConfig(), nil
	}

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return DefaultConfig(), nil
		}
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	return &cfg, nil
}

// Save saves configuration to a file
func (c *Config) Save(path string) error {
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	if err := os.WriteFile(path, data, 0600); err != nil {
		return fmt.Errorf("failed to write config file: %w", err)
	}

	return nil
}

// GetEnabledProviders returns a list of enabled provider names
func (c *Config) GetEnabledProviders() []string {
	var providers []string
	for name, p := range c.Providers {
		if p.Enabled {
			providers = append(providers, name)
		}
	}
	return providers
}

// DefaultConfig returns a config with sensible defaults
func DefaultConfig() *Config {
	return &Config{
		Version: "1.0",
		Defaults: Defaults{
			RefreshInterval: Duration(30 * time.Second),
			OutputFormat:    "table",
			ShowCached:      true,
		},
		Output: OutputConfig{
			ColorEnabled: true,
			Timestamps:   true,
		},
		Cache: CacheConfig{
			Enabled: true,
			Backend: "memory",
			TTL:     Duration(5 * time.Minute),
			MaxSize: 1000,
		},
		Providers: make(map[string]Provider),
	}
}

// GenerateSampleConfig creates a sample configuration file
func GenerateSampleConfig() *Config {
	return &Config{
		Version: "1.0",
		Defaults: Defaults{
			RefreshInterval: Duration(30 * time.Second),
			OutputFormat:    "table",
			ShowCached:      true,
		},
		Output: OutputConfig{
			ColorEnabled: true,
			Timestamps:   true,
			Columns: map[string][]string{
				"compute": {"name", "status", "cpu", "memory", "region"},
				"gpu":     {"name", "gpu_type", "gpu_count", "utilization", "price"},
			},
		},
		Cache: CacheConfig{
			Enabled: true,
			Backend: "memory",
			TTL:     Duration(5 * time.Minute),
			MaxSize: 1000,
		},
		Providers: map[string]Provider{
			"cloudflare": {
				Enabled: true,
				Auth: AuthConfig{
					Method:    "api_key",
					EnvAPIKey: "CLOUDFLARE_API_TOKEN",
				},
				Services: []string{"workers", "r2", "ai"},
				RateLimit: &RateLimitConfig{
					RequestsPerSecond: 4,
					Burst:             10,
					Timeout:           Duration(30 * time.Second),
				},
				Options: map[string]interface{}{
					"account_id": "your-account-id",
				},
			},
			"oracle": {
				Enabled: true,
				Auth: AuthConfig{
					Method:  "service_account",
					KeyFile: "~/.oci/config",
				},
				Regions:  []string{"us-ashburn-1", "us-phoenix-1"},
				Services: []string{"compute", "containers", "autonomous_db"},
				RateLimit: &RateLimitConfig{
					RequestsPerSecond: 10,
					Burst:             20,
					Timeout:           Duration(30 * time.Second),
				},
				Options: map[string]interface{}{
					"compartment_id": "your-compartment-ocid",
				},
			},
			"neon": {
				Enabled: true,
				Auth: AuthConfig{
					Method:    "api_key",
					EnvAPIKey: "NEON_API_KEY",
				},
			},
			"vastai": {
				Enabled: true,
				Auth: AuthConfig{
					Method:    "api_key",
					EnvAPIKey: "VASTAI_API_KEY",
				},
			},
			"runpod": {
				Enabled: true,
				Auth: AuthConfig{
					Method:    "api_key",
					EnvAPIKey: "RUNPOD_API_KEY",
				},
			},
			"azure": {
				Enabled: false,
				Auth: AuthConfig{
					Method:  "service_account",
					KeyFile: "~/.azure/credentials.json",
				},
				Services: []string{"vms", "aks", "functions"},
				Options: map[string]interface{}{
					"subscription_id": "your-subscription-id",
				},
			},
			"gcp": {
				Enabled: false,
				Auth: AuthConfig{
					Method:  "service_account",
					KeyFile: "~/.gcp/service-account.json",
				},
				Services: []string{"compute", "gke", "functions"},
				Options: map[string]interface{}{
					"project_id": "your-project-id",
				},
			},
		},
	}
}
