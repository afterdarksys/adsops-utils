load("../../lib/host.star", "host_info")

base_url = sys.config.get("statsagent_url")
if not base_url:
    print("ERROR: statsagent_url not configured")
    healthy = False
else:
    resp = sys.net.http_get(base_url + "/health")
    healthy = (resp["status_code"] == 200)
info = host_info()
print("host:", info["hostname"], "statsagent healthy:", healthy)
