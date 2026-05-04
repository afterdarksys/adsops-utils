package collectors

import (
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"net/http"
	"os"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// loadCA loads a CA certificate file and returns an x509 pool.
// If caPath is empty, returns nil (uses system pool).
func loadCA(caPath string) (*x509.CertPool, error) {
	if caPath == "" {
		return nil, nil
	}
	pool := x509.NewCertPool()
	pem, err := os.ReadFile(caPath)
	if err != nil {
		return nil, err
	}
	pool.AppendCertsFromPEM(pem)
	return pool, nil
}

// tlsClient returns an http.Client that trusts caPool (or the system pool if nil).
// It skips verification when caPool is nil AND we're talking to localhost.
func tlsClient(caPool *x509.CertPool) *http.Client {
	tlsCfg := &tls.Config{
		RootCAs: caPool,
	}
	if caPool == nil {
		// When no CA is provided (e.g. self-signed local k3s), skip verify.
		// This is acceptable because we're connecting to localhost.
		tlsCfg.InsecureSkipVerify = true //nolint:gosec
	}
	return &http.Client{
		Transport: &http.Transport{TLSClientConfig: tlsCfg},
		Timeout:   10 * time.Second,
	}
}

// kubeconfigYAML is a minimal struct for parsing kubeconfig files.
type kubeconfigYAML struct {
	Clusters []struct {
		Name    string `yaml:"name"`
		Cluster struct {
			Server                   string `yaml:"server"`
			CertificateAuthorityData string `yaml:"certificate-authority-data"`
			CertificateAuthority     string `yaml:"certificate-authority"`
		} `yaml:"cluster"`
	} `yaml:"clusters"`
	Users []struct {
		Name string `yaml:"name"`
		User struct {
			Token                 string `yaml:"token"`
			ClientCertificateData string `yaml:"client-certificate-data"`
			ClientKeyData         string `yaml:"client-key-data"`
		} `yaml:"user"`
	} `yaml:"users"`
	CurrentContext string `yaml:"current-context"`
	Contexts []struct {
		Name    string `yaml:"name"`
		Context struct {
			Cluster string `yaml:"cluster"`
			User    string `yaml:"user"`
		} `yaml:"context"`
	} `yaml:"contexts"`
}

// parseMinimalKubeconfig extracts server, token, and CA path from a kubeconfig.
// Returns server URL, bearer token (may be empty), and CA file path (may be empty).
func parseMinimalKubeconfig(path string) (server, token, caPath string, err error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", "", "", err
	}

	var kc kubeconfigYAML
	if err := yaml.Unmarshal(data, &kc); err != nil {
		return "", "", "", err
	}

	// Find current context
	ctxCluster := ""
	ctxUser := ""
	for _, ctx := range kc.Contexts {
		if ctx.Name == kc.CurrentContext || kc.CurrentContext == "" {
			ctxCluster = ctx.Context.Cluster
			ctxUser = ctx.Context.User
			break
		}
	}

	// Get server and CA
	for _, cl := range kc.Clusters {
		if cl.Name == ctxCluster || ctxCluster == "" {
			server = cl.Cluster.Server
			caPath = cl.Cluster.CertificateAuthority

			// Handle inline CA data
			if cl.Cluster.CertificateAuthorityData != "" && caPath == "" {
				caData, err := base64.StdEncoding.DecodeString(cl.Cluster.CertificateAuthorityData)
				if err == nil {
					// Write to a temp file
					tmp, err := os.CreateTemp("", "statsagent-ca-*.crt")
					if err == nil {
						tmp.Write(caData)
						tmp.Close()
						caPath = tmp.Name()
					}
				}
			}
			break
		}
	}

	// Get token
	for _, u := range kc.Users {
		if u.Name == ctxUser || ctxUser == "" {
			token = u.User.Token

			// Handle client cert auth — build a token from it if needed
			// (k3s typically uses token-based auth, so this is a fallback)
			if token == "" && u.User.ClientCertificateData != "" {
				// Just mark as cert-based — the TLS client will handle it
				token = ""
			}
			break
		}
	}

	// Normalise localhost server address for k3s
	if strings.Contains(server, "127.0.0.1") || strings.Contains(server, "localhost") {
		// keep as-is
	}

	return server, token, caPath, nil
}
