package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// --- Docker Handlers ---

// ListContainers returns all Docker containers on the host.
// GET /v1/infra/docker/containers
// TODO:
//  1. client.NewClientWithOpts(client.WithHost("unix:///var/run/docker.sock"), client.WithAPIVersionNegotiation())
//  2. ContainerList(ctx, container.ListOptions{All: true})
//  3. Return container ID, name, image, status, state, ports
func ListContainers(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// GetContainerLogs returns recent log lines for a container.
// GET /v1/infra/docker/containers/:id/logs
// TODO:
//  1. Parse query param tail (default "100"), stream=false
//  2. ContainerLogs(ctx, id, container.LogsOptions{ShowStdout: true, ShowStderr: true, Tail: tail})
//  3. Strip docker multiplexed stream header (8-byte prefix) from each line
func GetContainerLogs(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// ContainerAction starts, stops, or restarts a container.
// POST /v1/infra/docker/containers/:id/:action
// action must be one of: start, stop, restart — validate before calling Docker SDK.
// TODO:
//  1. Validate :action is in allowlist {"start", "stop", "restart"} — 400 if invalid
//  2. ContainerStart / ContainerStop / ContainerRestart accordingly
//  3. Return 204 on success
func ContainerAction(c *gin.Context) {
	action := c.Param("action")
	allowed := map[string]bool{"start": true, "stop": true, "restart": true}
	if !allowed[action] {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": gin.H{
				"code":      "INVALID_ACTION",
				"message":   "Action must be one of: start, stop, restart",
				"timestamp": time.Now().UTC().Format(time.RFC3339),
			},
		})
		return
	}
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// --- Kubernetes Handlers ---

// ListPods returns pods in the given namespace.
// GET /v1/infra/k8s/pods?namespace=default
// TODO:
//  1. rest.InClusterConfig() with clientcmd.BuildConfigFromFlags fallback for local dev
//  2. kubernetes.NewForConfig(config)
//  3. clientset.CoreV1().Pods(namespace).List(ctx, metav1.ListOptions{})
func ListPods(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// ListDeployments returns deployments in the given namespace.
// GET /v1/infra/k8s/deployments?namespace=default
// TODO: clientset.AppsV1().Deployments(namespace).List(ctx, metav1.ListOptions{})
func ListDeployments(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// ScaleDeployment sets the replica count for a deployment.
// POST /v1/infra/k8s/deployments/:name/scale
// Body: {replicas: int}
// TODO:
//  1. Validate replicas >= 0
//  2. clientset.AppsV1().Deployments(namespace).GetScale(ctx, name, metav1.GetOptions{})
//  3. Set scale.Spec.Replicas = int32(replicas), UpdateScale(ctx, name, scale, metav1.UpdateOptions{})
func ScaleDeployment(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// GetPodLogs returns recent log lines for a pod.
// GET /v1/infra/k8s/pods/:name/logs?namespace=default&tail=100&container=
// TODO:
//  1. Parse query params: namespace, tail (default 100), container (optional)
//  2. clientset.CoreV1().Pods(namespace).GetLogs(name, &corev1.PodLogOptions{TailLines: &tail, Container: container})
//  3. Read stream to string, return as {logs: string}
func GetPodLogs(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}

// --- System Metrics Handler ---

// GetSystemMetrics returns CPU, memory, and disk usage for the host.
// GET /v1/infra/system/metrics
// Returns: {cpu_percent, mem_total, mem_used, mem_percent, disk_total, disk_used, disk_percent}
// TODO:
//  1. cpu.Percent(0, false) → cpu_percent (0-100 aggregate)
//  2. mem.VirtualMemory() → mem_total, mem_used, mem_percent
//  3. disk.Usage("/") → disk_total, disk_used, disk_percent
func GetSystemMetrics(c *gin.Context) {
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": gin.H{
			"code":      "NOT_IMPLEMENTED",
			"message":   "This endpoint is not yet implemented",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
	})
}
