import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from adsops.v1 import container_pb2 as _container_pb2
from adsops.v1 import k3s_pb2 as _k3s_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SystemStats(_message.Message):
    __slots__ = ("hostname", "uptime_seconds", "load_avg_1m", "load_avg_5m", "load_avg_15m", "cpu_used_pct", "cpu_idle_pct", "cpu_iowait_pct", "cpu_cores", "mem_total_bytes", "mem_available_bytes", "mem_used_bytes", "mem_used_pct", "mem_cached_bytes", "mem_buffers_bytes", "swap_total_bytes", "swap_used_bytes", "swap_used_pct")
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    UPTIME_SECONDS_FIELD_NUMBER: _ClassVar[int]
    LOAD_AVG_1M_FIELD_NUMBER: _ClassVar[int]
    LOAD_AVG_5M_FIELD_NUMBER: _ClassVar[int]
    LOAD_AVG_15M_FIELD_NUMBER: _ClassVar[int]
    CPU_USED_PCT_FIELD_NUMBER: _ClassVar[int]
    CPU_IDLE_PCT_FIELD_NUMBER: _ClassVar[int]
    CPU_IOWAIT_PCT_FIELD_NUMBER: _ClassVar[int]
    CPU_CORES_FIELD_NUMBER: _ClassVar[int]
    MEM_TOTAL_BYTES_FIELD_NUMBER: _ClassVar[int]
    MEM_AVAILABLE_BYTES_FIELD_NUMBER: _ClassVar[int]
    MEM_USED_BYTES_FIELD_NUMBER: _ClassVar[int]
    MEM_USED_PCT_FIELD_NUMBER: _ClassVar[int]
    MEM_CACHED_BYTES_FIELD_NUMBER: _ClassVar[int]
    MEM_BUFFERS_BYTES_FIELD_NUMBER: _ClassVar[int]
    SWAP_TOTAL_BYTES_FIELD_NUMBER: _ClassVar[int]
    SWAP_USED_BYTES_FIELD_NUMBER: _ClassVar[int]
    SWAP_USED_PCT_FIELD_NUMBER: _ClassVar[int]
    hostname: str
    uptime_seconds: float
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    cpu_used_pct: float
    cpu_idle_pct: float
    cpu_iowait_pct: float
    cpu_cores: int
    mem_total_bytes: int
    mem_available_bytes: int
    mem_used_bytes: int
    mem_used_pct: float
    mem_cached_bytes: int
    mem_buffers_bytes: int
    swap_total_bytes: int
    swap_used_bytes: int
    swap_used_pct: float
    def __init__(self, hostname: _Optional[str] = ..., uptime_seconds: _Optional[float] = ..., load_avg_1m: _Optional[float] = ..., load_avg_5m: _Optional[float] = ..., load_avg_15m: _Optional[float] = ..., cpu_used_pct: _Optional[float] = ..., cpu_idle_pct: _Optional[float] = ..., cpu_iowait_pct: _Optional[float] = ..., cpu_cores: _Optional[int] = ..., mem_total_bytes: _Optional[int] = ..., mem_available_bytes: _Optional[int] = ..., mem_used_bytes: _Optional[int] = ..., mem_used_pct: _Optional[float] = ..., mem_cached_bytes: _Optional[int] = ..., mem_buffers_bytes: _Optional[int] = ..., swap_total_bytes: _Optional[int] = ..., swap_used_bytes: _Optional[int] = ..., swap_used_pct: _Optional[float] = ...) -> None: ...

class MountStats(_message.Message):
    __slots__ = ("device", "mount_point", "fstype", "total_bytes", "used_bytes", "free_bytes", "used_pct")
    DEVICE_FIELD_NUMBER: _ClassVar[int]
    MOUNT_POINT_FIELD_NUMBER: _ClassVar[int]
    FSTYPE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BYTES_FIELD_NUMBER: _ClassVar[int]
    USED_BYTES_FIELD_NUMBER: _ClassVar[int]
    FREE_BYTES_FIELD_NUMBER: _ClassVar[int]
    USED_PCT_FIELD_NUMBER: _ClassVar[int]
    device: str
    mount_point: str
    fstype: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_pct: float
    def __init__(self, device: _Optional[str] = ..., mount_point: _Optional[str] = ..., fstype: _Optional[str] = ..., total_bytes: _Optional[int] = ..., used_bytes: _Optional[int] = ..., free_bytes: _Optional[int] = ..., used_pct: _Optional[float] = ...) -> None: ...

class IOStats(_message.Message):
    __slots__ = ("device", "reads_per_sec", "writes_per_sec", "read_bytes_per_sec", "write_bytes_per_sec", "await_ms", "util_pct")
    DEVICE_FIELD_NUMBER: _ClassVar[int]
    READS_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    WRITES_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    READ_BYTES_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    WRITE_BYTES_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    AWAIT_MS_FIELD_NUMBER: _ClassVar[int]
    UTIL_PCT_FIELD_NUMBER: _ClassVar[int]
    device: str
    reads_per_sec: float
    writes_per_sec: float
    read_bytes_per_sec: float
    write_bytes_per_sec: float
    await_ms: float
    util_pct: float
    def __init__(self, device: _Optional[str] = ..., reads_per_sec: _Optional[float] = ..., writes_per_sec: _Optional[float] = ..., read_bytes_per_sec: _Optional[float] = ..., write_bytes_per_sec: _Optional[float] = ..., await_ms: _Optional[float] = ..., util_pct: _Optional[float] = ...) -> None: ...

class DiskStats(_message.Message):
    __slots__ = ("mounts", "devices")
    MOUNTS_FIELD_NUMBER: _ClassVar[int]
    DEVICES_FIELD_NUMBER: _ClassVar[int]
    mounts: _containers.RepeatedCompositeFieldContainer[MountStats]
    devices: _containers.RepeatedCompositeFieldContainer[IOStats]
    def __init__(self, mounts: _Optional[_Iterable[_Union[MountStats, _Mapping]]] = ..., devices: _Optional[_Iterable[_Union[IOStats, _Mapping]]] = ...) -> None: ...

class InterfaceStat(_message.Message):
    __slots__ = ("name", "rx_bytes_per_sec", "tx_bytes_per_sec", "rx_pkts_per_sec", "tx_pkts_per_sec", "rx_errors", "tx_errors", "rx_dropped", "tx_dropped", "rx_total_bytes", "tx_total_bytes")
    NAME_FIELD_NUMBER: _ClassVar[int]
    RX_BYTES_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    TX_BYTES_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    RX_PKTS_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    TX_PKTS_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    RX_ERRORS_FIELD_NUMBER: _ClassVar[int]
    TX_ERRORS_FIELD_NUMBER: _ClassVar[int]
    RX_DROPPED_FIELD_NUMBER: _ClassVar[int]
    TX_DROPPED_FIELD_NUMBER: _ClassVar[int]
    RX_TOTAL_BYTES_FIELD_NUMBER: _ClassVar[int]
    TX_TOTAL_BYTES_FIELD_NUMBER: _ClassVar[int]
    name: str
    rx_bytes_per_sec: float
    tx_bytes_per_sec: float
    rx_pkts_per_sec: float
    tx_pkts_per_sec: float
    rx_errors: int
    tx_errors: int
    rx_dropped: int
    tx_dropped: int
    rx_total_bytes: int
    tx_total_bytes: int
    def __init__(self, name: _Optional[str] = ..., rx_bytes_per_sec: _Optional[float] = ..., tx_bytes_per_sec: _Optional[float] = ..., rx_pkts_per_sec: _Optional[float] = ..., tx_pkts_per_sec: _Optional[float] = ..., rx_errors: _Optional[int] = ..., tx_errors: _Optional[int] = ..., rx_dropped: _Optional[int] = ..., tx_dropped: _Optional[int] = ..., rx_total_bytes: _Optional[int] = ..., tx_total_bytes: _Optional[int] = ...) -> None: ...

class NetworkStats(_message.Message):
    __slots__ = ("interfaces",)
    INTERFACES_FIELD_NUMBER: _ClassVar[int]
    interfaces: _containers.RepeatedCompositeFieldContainer[InterfaceStat]
    def __init__(self, interfaces: _Optional[_Iterable[_Union[InterfaceStat, _Mapping]]] = ...) -> None: ...

class ProcInfo(_message.Message):
    __slots__ = ("pid", "name", "state", "cpu_pct", "mem_rss_bytes", "mem_pct")
    PID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    CPU_PCT_FIELD_NUMBER: _ClassVar[int]
    MEM_RSS_BYTES_FIELD_NUMBER: _ClassVar[int]
    MEM_PCT_FIELD_NUMBER: _ClassVar[int]
    pid: int
    name: str
    state: str
    cpu_pct: float
    mem_rss_bytes: int
    mem_pct: float
    def __init__(self, pid: _Optional[int] = ..., name: _Optional[str] = ..., state: _Optional[str] = ..., cpu_pct: _Optional[float] = ..., mem_rss_bytes: _Optional[int] = ..., mem_pct: _Optional[float] = ...) -> None: ...

class ProcessStats(_message.Message):
    __slots__ = ("total_procs", "running_procs", "zombie_procs", "top_cpu", "top_mem")
    TOTAL_PROCS_FIELD_NUMBER: _ClassVar[int]
    RUNNING_PROCS_FIELD_NUMBER: _ClassVar[int]
    ZOMBIE_PROCS_FIELD_NUMBER: _ClassVar[int]
    TOP_CPU_FIELD_NUMBER: _ClassVar[int]
    TOP_MEM_FIELD_NUMBER: _ClassVar[int]
    total_procs: int
    running_procs: int
    zombie_procs: int
    top_cpu: _containers.RepeatedCompositeFieldContainer[ProcInfo]
    top_mem: _containers.RepeatedCompositeFieldContainer[ProcInfo]
    def __init__(self, total_procs: _Optional[int] = ..., running_procs: _Optional[int] = ..., zombie_procs: _Optional[int] = ..., top_cpu: _Optional[_Iterable[_Union[ProcInfo, _Mapping]]] = ..., top_mem: _Optional[_Iterable[_Union[ProcInfo, _Mapping]]] = ...) -> None: ...

class StatsSnapshot(_message.Message):
    __slots__ = ("timestamp", "context", "system", "disk", "network", "process", "docker", "k3s")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_FIELD_NUMBER: _ClassVar[int]
    DISK_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    PROCESS_FIELD_NUMBER: _ClassVar[int]
    DOCKER_FIELD_NUMBER: _ClassVar[int]
    K3S_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    context: str
    system: SystemStats
    disk: DiskStats
    network: NetworkStats
    process: ProcessStats
    docker: _container_pb2.DockerStats
    k3s: _k3s_pb2.K3sStats
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., context: _Optional[str] = ..., system: _Optional[_Union[SystemStats, _Mapping]] = ..., disk: _Optional[_Union[DiskStats, _Mapping]] = ..., network: _Optional[_Union[NetworkStats, _Mapping]] = ..., process: _Optional[_Union[ProcessStats, _Mapping]] = ..., docker: _Optional[_Union[_container_pb2.DockerStats, _Mapping]] = ..., k3s: _Optional[_Union[_k3s_pb2.K3sStats, _Mapping]] = ...) -> None: ...
