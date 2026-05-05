load("../../lib/host.star", "host_info")

base_url = sys.config.get("statsagent_url")
resp = sys.net.http_get(base_url + "/health")
healthy = (resp["status_code"] == 200)
info = host_info()
print("host:", info["hostname"], "statsagent healthy:", healthy)
