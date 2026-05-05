def container_list():
    """Return list of all containers via sys.containers."""
    return sys.containers.list()

def container_stats(name):
    """Return stats dict for a specific container."""
    return sys.containers.stats(name)

def container_count():
    """Return count of running containers."""
    containers = sys.containers.list()
    return len([c for c in containers if c.get("state") == "running"])
