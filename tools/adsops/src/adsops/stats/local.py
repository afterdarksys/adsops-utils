import platform
import time
import datetime
import psutil
from google.protobuf.timestamp_pb2 import Timestamp
from adsops.v1 import stats_pb2


def collect_once() -> stats_pb2.StatsSnapshot:
    """Collect local system metrics, return StatsSnapshot proto (D-11)."""
    snap = stats_pb2.StatsSnapshot()

    # Timestamp
    ts = Timestamp()
    ts.FromDatetime(datetime.datetime.now(tz=datetime.timezone.utc))
    snap.timestamp.CopyFrom(ts)

    snap.context = platform.node()

    # System stats
    sys_stats = stats_pb2.SystemStats()
    sys_stats.hostname = platform.node()
    sys_stats.cpu_cores = psutil.cpu_count() or 0
    cpu_pct = psutil.cpu_percent(interval=1)
    sys_stats.cpu_used_pct = cpu_pct
    sys_stats.cpu_idle_pct = 100.0 - cpu_pct

    mem = psutil.virtual_memory()
    sys_stats.mem_total_bytes = mem.total
    sys_stats.mem_available_bytes = mem.available
    sys_stats.mem_used_bytes = mem.used
    sys_stats.mem_used_pct = mem.percent
    sys_stats.mem_cached_bytes = getattr(mem, "cached", 0)
    sys_stats.mem_buffers_bytes = getattr(mem, "buffers", 0)

    swap = psutil.swap_memory()
    sys_stats.swap_total_bytes = swap.total
    sys_stats.swap_used_bytes = swap.used
    sys_stats.swap_used_pct = swap.percent

    load = psutil.getloadavg()
    sys_stats.load_avg_1m = load[0]
    sys_stats.load_avg_5m = load[1]
    sys_stats.load_avg_15m = load[2]

    # Boot time for uptime (T-02-11: bounded by psutil.boot_time(), no unbounded wait)
    sys_stats.uptime_seconds = time.time() - psutil.boot_time()

    snap.system.CopyFrom(sys_stats)

    # Disk stats — catch OSError/PermissionError per T-02-11
    disk_stats = stats_pb2.DiskStats()
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            mount = stats_pb2.MountStats(
                device=part.device,
                mount_point=part.mountpoint,
                fstype=part.fstype,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                used_pct=usage.percent,
            )
            disk_stats.mounts.append(mount)
        except (PermissionError, OSError):
            continue
    snap.disk.CopyFrom(disk_stats)

    # Network stats
    net_stats = stats_pb2.NetworkStats()
    net_io = psutil.net_io_counters(pernic=True)
    for iface, counters in net_io.items():
        iface_stat = stats_pb2.InterfaceStat(
            name=iface,
            rx_total_bytes=counters.bytes_recv,
            tx_total_bytes=counters.bytes_sent,
        )
        net_stats.interfaces.append(iface_stat)
    snap.network.CopyFrom(net_stats)

    # Process stats
    proc_stats = stats_pb2.ProcessStats()
    proc_stats.total_procs = len(psutil.pids())
    snap.process.CopyFrom(proc_stats)

    return snap
