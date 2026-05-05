def k3s_node_list():
    """Return list of k3s nodes."""
    return sys.k3s.nodes()

def k3s_pod_list(namespace=None):
    """Return list of pods, optionally filtered by namespace."""
    if namespace:
        return sys.k3s.pods(namespace)
    return sys.k3s.pods()

def k3s_healthy():
    """Return True if all nodes are ready."""
    nodes = sys.k3s.nodes()
    return all(n.get("ready", False) for n in nodes)
