// Package inventory provides access to the hostctl inventory database.
// Falls back to ~/.ssh/config if the database is unavailable.
package inventory

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"

	_ "github.com/lib/pq"

	sshcfg "github.com/afterdarksys/adsops-utils/tools/infractl/ssh"
)

// HostRecord is a slim view of an inventory resource.
type HostRecord struct {
	Hostname     string
	IP           string
	Type         string
	Status       string
	Environment  string
	HasDocker    bool
	HasK3s       bool
	SSHUser      string
	SSHPort      string
	SSHKey       string
}

var db *sql.DB

func initDB() error {
	if db != nil {
		return nil
	}
	host := envOrDefault("INVENTORY_DB_HOST", "afterdarksys.com")
	port := envOrDefault("INVENTORY_DB_PORT", "5432")
	dbname := envOrDefault("INVENTORY_DB_NAME", "inventory")
	user := os.Getenv("INVENTORY_DB_USER")
	password := os.Getenv("INVENTORY_DB_PASSWORD")

	if user == "" || password == "" {
		return fmt.Errorf("INVENTORY_DB_USER / INVENTORY_DB_PASSWORD not set")
	}

	dsn := fmt.Sprintf("host=%s port=%s dbname=%s user=%s password=%s sslmode=require",
		host, port, dbname, user, password)

	var err error
	db, err = sql.Open("postgres", dsn)
	if err != nil {
		return err
	}
	return db.Ping()
}

// GetHost returns a HostRecord for the given hostname.
// Tries the inventory DB first; falls back to ~/.ssh/config.
func GetHost(hostname string) (*HostRecord, error) {
	if err := initDB(); err == nil {
		rec, err := dbGetHost(hostname)
		if err == nil {
			return rec, nil
		}
	}
	// Fallback: look up in SSH config
	entry := sshcfg.LookupHost(hostname)
	return &HostRecord{
		Hostname: hostname,
		IP:       entry.Target,
		SSHUser:  entry.User,
		SSHPort:  entry.Port,
		SSHKey:   entry.IdentityFile,
	}, nil
}

// ListHosts returns all hosts from the inventory.
// Falls back to SSH config entries if DB is unavailable.
func ListHosts() ([]*HostRecord, error) {
	if err := initDB(); err == nil {
		hosts, err := dbListHosts()
		if err == nil {
			return hosts, nil
		}
	}
	return sshConfigHosts()
}

func dbGetHost(hostname string) (*HostRecord, error) {
	query := `
		SELECT hostname, metadata, type, status, environment
		FROM inventory_resources WHERE hostname = $1
	`
	var metaData []byte
	rec := &HostRecord{}
	err := db.QueryRow(query, hostname).Scan(&rec.Hostname, &metaData, &rec.Type, &rec.Status, &rec.Environment)
	if err != nil {
		return nil, err
	}
	applyMeta(rec, metaData)
	return rec, nil
}

func dbListHosts() ([]*HostRecord, error) {
	query := `
		SELECT hostname, metadata, type, status, environment
		FROM inventory_resources
		WHERE type IN ('server','vm','k8s-node','other')
		ORDER BY hostname
	`
	rows, err := db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var hosts []*HostRecord
	for rows.Next() {
		var metaData []byte
		rec := &HostRecord{}
		if err := rows.Scan(&rec.Hostname, &metaData, &rec.Type, &rec.Status, &rec.Environment); err != nil {
			continue
		}
		applyMeta(rec, metaData)
		hosts = append(hosts, rec)
	}
	return hosts, rows.Err()
}

func applyMeta(rec *HostRecord, metaData []byte) {
	if len(metaData) == 0 {
		return
	}
	var meta map[string]interface{}
	if json.Unmarshal(metaData, &meta) != nil {
		return
	}
	if v, ok := meta["ip"].(string); ok {
		rec.IP = v
	}
	if v, ok := meta["ssh_user"].(string); ok {
		rec.SSHUser = v
	}
	if v, ok := meta["ssh_port"].(string); ok {
		rec.SSHPort = v
	}
	if v, ok := meta["ssh_key"].(string); ok {
		rec.SSHKey = v
	}
	if v, ok := meta["has_docker"].(bool); ok {
		rec.HasDocker = v
	}
	if v, ok := meta["has_k3s"].(bool); ok {
		rec.HasK3s = v
	}
}

func sshConfigHosts() ([]*HostRecord, error) {
	entries, err := sshcfg.ParseConfig("")
	if err != nil {
		return nil, err
	}
	var hosts []*HostRecord
	for _, e := range entries {
		hosts = append(hosts, &HostRecord{
			Hostname: e.Name,
			IP:       e.HostName,
			SSHUser:  e.User,
			SSHPort:  e.Port,
			SSHKey:   e.IdentityFile,
		})
	}
	return hosts, nil
}

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
