load("../../lib/host.star", "host_info")

base_url = sys.config.get("changes_api_url")
if not base_url:
    print("ERROR: changes_api_url not configured")
else:
    resp = sys.net.http_get(base_url + "/metrics")
    body = resp["body"]

    request_count = None
    latency_sum = None
    latency_count = None

    for line in body.split("\n"):
        if line.startswith("#") or line == "":
            continue
        if line.startswith("http_requests_total"):
            parts = line.split(" ")
            if len(parts) >= 2:
                request_count = parts[-1]
        if line.startswith("http_request_duration_seconds_sum"):
            latency_sum = line.split(" ")[-1]
        if line.startswith("http_request_duration_seconds_count"):
            latency_count = line.split(" ")[-1]

    latency_avg = 0.0
    if latency_sum and latency_count and float(latency_count) > 0:
        latency_avg = float(latency_sum) / float(latency_count)

    info = host_info()
    print("host:", info["hostname"])
    print("request_count:", request_count if request_count is not None else "N/A (metric not found)")
    print("latency_avg_seconds:", latency_avg)
