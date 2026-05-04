package cmd

import (
	"bytes"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/spf13/cobra"

	"github.com/afterdarksys/adsops-utils/tools/statsagent/output"
)

// NewPushCommand returns the `push` subcommand.
func NewPushCommand() *cobra.Command {
	cfg := DefaultConfig()
	var endpoint string
	var interval string

	cmd := &cobra.Command{
		Use:   "push [endpoint]",
		Short: "Collect metrics and push JSON to a remote endpoint on an interval",
		Long: `Collect metrics every INTERVAL and POST them as JSON to ENDPOINT.

The endpoint receives a JSON body identical to GET /stats.

Examples:
  statsagent push https://collector.example.com/ingest
  statsagent push --interval 60s https://collector.example.com/ingest`,
		Args: cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 1 {
				endpoint = args[0]
			} else if cfg.PushEndpoint != "" {
				endpoint = cfg.PushEndpoint
			} else {
				return fmt.Errorf("endpoint required (arg or $STATSAGENT_PUSH_ENDPOINT)")
			}
			if interval != "" {
				d, err := time.ParseDuration(interval)
				if err != nil {
					return fmt.Errorf("invalid interval: %w", err)
				}
				cfg.PushInterval = d
			}
			return runPush(cfg, endpoint)
		},
	}

	cmd.Flags().StringVar(&interval, "interval", "", "Push interval (e.g. 30s, 1m)")

	return cmd
}

func runPush(cfg *Config, endpoint string) error {
	log.Printf("statsagent push  endpoint=%s  interval=%s", endpoint, cfg.PushInterval)

	// Prime collectors
	collect(cfg)

	ticker := time.NewTicker(cfg.PushInterval)
	defer ticker.Stop()

	for {
		snap := collect(cfg)
		if err := pushSnapshot(endpoint, snap); err != nil {
			log.Printf("push error: %v", err)
		} else {
			log.Printf("pushed snapshot ts=%s", snap.Timestamp.Format(time.RFC3339))
		}
		<-ticker.C
	}
}

func pushSnapshot(endpoint string, snap *output.StatsSnapshot) error {
	var buf bytes.Buffer
	if err := output.WriteJSONCompact(&buf, snap); err != nil {
		return fmt.Errorf("marshal: %w", err)
	}

	resp, err := http.Post(endpoint, "application/json", &buf) //nolint:noctx
	if err != nil {
		return fmt.Errorf("post: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("server returned %d", resp.StatusCode)
	}
	return nil
}
