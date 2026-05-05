def host_info():
    """Return dict with hostname and OS."""
    code, out, err = sys.exec.run("hostname")
    hostname = out.strip() if code == 0 else "unknown"
    code2, out2, err2 = sys.exec.run("uname -s")
    os_name = out2.strip() if code2 == 0 else "unknown"
    return {"hostname": hostname, "os": os_name}

def host_uptime():
    """Return raw uptime string."""
    code, out, err = sys.exec.run("uptime")
    return out.strip() if code == 0 else "unknown"
