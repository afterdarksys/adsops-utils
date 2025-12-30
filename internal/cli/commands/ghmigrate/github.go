package ghmigrate

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// GitHubIssue represents a GitHub issue
type GitHubIssue struct {
	Number    int           `json:"number"`
	Title     string        `json:"title"`
	Body      string        `json:"body"`
	State     string        `json:"state"`
	Labels    []GitHubLabel `json:"labels"`
	User      GitHubUser    `json:"user"`
	Assignee  *GitHubUser   `json:"assignee"`
	Assignees []GitHubUser  `json:"assignees"`
	CreatedAt time.Time     `json:"created_at"`
	UpdatedAt time.Time     `json:"updated_at"`
	ClosedAt  *time.Time    `json:"closed_at"`
	HTMLURL   string        `json:"html_url"`
	Comments  int           `json:"comments"`
}

// GitHubLabel represents a GitHub label
type GitHubLabel struct {
	Name        string `json:"name"`
	Color       string `json:"color"`
	Description string `json:"description"`
}

// GitHubUser represents a GitHub user
type GitHubUser struct {
	Login     string `json:"login"`
	AvatarURL string `json:"avatar_url"`
	HTMLURL   string `json:"html_url"`
}

// GitHubComment represents a GitHub issue comment
type GitHubComment struct {
	ID        int64      `json:"id"`
	Body      string     `json:"body"`
	User      GitHubUser `json:"user"`
	CreatedAt time.Time  `json:"created_at"`
	UpdatedAt time.Time  `json:"updated_at"`
}

// GitHubClient handles GitHub API interactions
type GitHubClient struct {
	BaseURL    string
	Token      string
	Username   string
	HTTPClient *http.Client
}

// NewGitHubClient creates a new GitHub API client
func NewGitHubClient(baseURL, token, username string) *GitHubClient {
	if baseURL == "" {
		baseURL = "https://api.github.com"
	}
	// Remove trailing slash
	baseURL = strings.TrimSuffix(baseURL, "/")

	return &GitHubClient{
		BaseURL:    baseURL,
		Token:      token,
		Username:   username,
		HTTPClient: &http.Client{Timeout: 30 * time.Second},
	}
}

// doRequest performs an authenticated HTTP request
func (c *GitHubClient) doRequest(method, endpoint string) ([]byte, error) {
	reqURL := c.BaseURL + endpoint

	req, err := http.NewRequest(method, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	return body, nil
}

// ListIssues fetches issues from a repository
func (c *GitHubClient) ListIssues(owner, repo string, state string, labels []string, limit int) ([]GitHubIssue, error) {
	var allIssues []GitHubIssue
	page := 1
	perPage := 100
	if limit < perPage {
		perPage = limit
	}

	for len(allIssues) < limit {
		params := url.Values{}
		params.Set("state", state)
		params.Set("per_page", fmt.Sprintf("%d", perPage))
		params.Set("page", fmt.Sprintf("%d", page))
		params.Set("sort", "created")
		params.Set("direction", "desc")

		if len(labels) > 0 {
			params.Set("labels", strings.Join(labels, ","))
		}

		endpoint := fmt.Sprintf("/repos/%s/%s/issues?%s", owner, repo, params.Encode())

		body, err := c.doRequest(http.MethodGet, endpoint)
		if err != nil {
			return nil, err
		}

		var issues []GitHubIssue
		if err := json.Unmarshal(body, &issues); err != nil {
			return nil, fmt.Errorf("failed to parse issues: %w", err)
		}

		// Filter out pull requests (GitHub returns PRs in issues API)
		for _, issue := range issues {
			// PRs have a pull_request field, but we're using a simplified struct
			// Check if the URL contains /pull/ which would indicate a PR
			if !strings.Contains(issue.HTMLURL, "/pull/") {
				allIssues = append(allIssues, issue)
			}
		}

		if len(issues) < perPage {
			break // No more pages
		}
		page++
	}

	// Trim to limit
	if len(allIssues) > limit {
		allIssues = allIssues[:limit]
	}

	return allIssues, nil
}

// GetIssueComments fetches comments for an issue
func (c *GitHubClient) GetIssueComments(owner, repo string, issueNumber int) ([]GitHubComment, error) {
	endpoint := fmt.Sprintf("/repos/%s/%s/issues/%d/comments?per_page=100", owner, repo, issueNumber)

	body, err := c.doRequest(http.MethodGet, endpoint)
	if err != nil {
		return nil, err
	}

	var comments []GitHubComment
	if err := json.Unmarshal(body, &comments); err != nil {
		return nil, fmt.Errorf("failed to parse comments: %w", err)
	}

	return comments, nil
}

// ParseRepoString parses "owner/repo" format into owner and repo
func ParseRepoString(repoStr string) (owner, repo string, err error) {
	parts := strings.Split(repoStr, "/")
	if len(parts) != 2 {
		return "", "", fmt.Errorf("invalid repo format: %s (expected owner/repo)", repoStr)
	}
	return parts[0], parts[1], nil
}
