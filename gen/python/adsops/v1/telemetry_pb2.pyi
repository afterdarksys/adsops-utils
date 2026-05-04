from adsops.v1 import container_pb2 as _container_pb2
from adsops.v1 import k3s_pb2 as _k3s_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HostInfo(_message.Message):
    __slots__ = ("hostname", "os", "platform", "uptime")
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    OS_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    hostname: str
    os: str
    platform: str
    uptime: int
    def __init__(self, hostname: _Optional[str] = ..., os: _Optional[str] = ..., platform: _Optional[str] = ..., uptime: _Optional[int] = ...) -> None: ...

class CpuMetrics(_message.Message):
    __slots__ = ("usage_percent", "cores")
    USAGE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    CORES_FIELD_NUMBER: _ClassVar[int]
    usage_percent: float
    cores: int
    def __init__(self, usage_percent: _Optional[float] = ..., cores: _Optional[int] = ...) -> None: ...

class MemoryMetrics(_message.Message):
    __slots__ = ("total", "used", "free", "used_percent")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    USED_FIELD_NUMBER: _ClassVar[int]
    FREE_FIELD_NUMBER: _ClassVar[int]
    USED_PERCENT_FIELD_NUMBER: _ClassVar[int]
    total: int
    used: int
    free: int
    used_percent: float
    def __init__(self, total: _Optional[int] = ..., used: _Optional[int] = ..., free: _Optional[int] = ..., used_percent: _Optional[float] = ...) -> None: ...

class DiskMetrics(_message.Message):
    __slots__ = ("path", "total", "used", "free", "used_percent")
    PATH_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    USED_FIELD_NUMBER: _ClassVar[int]
    FREE_FIELD_NUMBER: _ClassVar[int]
    USED_PERCENT_FIELD_NUMBER: _ClassVar[int]
    path: str
    total: int
    used: int
    free: int
    used_percent: float
    def __init__(self, path: _Optional[str] = ..., total: _Optional[int] = ..., used: _Optional[int] = ..., free: _Optional[int] = ..., used_percent: _Optional[float] = ...) -> None: ...

class NetworkMetrics(_message.Message):
    __slots__ = ("bytes_recv", "bytes_sent")
    BYTES_RECV_FIELD_NUMBER: _ClassVar[int]
    BYTES_SENT_FIELD_NUMBER: _ClassVar[int]
    bytes_recv: int
    bytes_sent: int
    def __init__(self, bytes_recv: _Optional[int] = ..., bytes_sent: _Optional[int] = ...) -> None: ...

class SoftwareInfo(_message.Message):
    __slots__ = ("name", "version")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: str
    def __init__(self, name: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class TelemetryPayload(_message.Message):
    __slots__ = ("timestamp", "host_id", "host_info", "cpu", "memory", "disk", "network", "software", "docker", "k3s")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    HOST_ID_FIELD_NUMBER: _ClassVar[int]
    HOST_INFO_FIELD_NUMBER: _ClassVar[int]
    CPU_FIELD_NUMBER: _ClassVar[int]
    MEMORY_FIELD_NUMBER: _ClassVar[int]
    DISK_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    SOFTWARE_FIELD_NUMBER: _ClassVar[int]
    DOCKER_FIELD_NUMBER: _ClassVar[int]
    K3S_FIELD_NUMBER: _ClassVar[int]
    timestamp: int
    host_id: str
    host_info: HostInfo
    cpu: CpuMetrics
    memory: MemoryMetrics
    disk: _containers.RepeatedCompositeFieldContainer[DiskMetrics]
    network: NetworkMetrics
    software: _containers.RepeatedCompositeFieldContainer[SoftwareInfo]
    docker: _container_pb2.DockerStats
    k3s: _k3s_pb2.K3sStats
    def __init__(self, timestamp: _Optional[int] = ..., host_id: _Optional[str] = ..., host_info: _Optional[_Union[HostInfo, _Mapping]] = ..., cpu: _Optional[_Union[CpuMetrics, _Mapping]] = ..., memory: _Optional[_Union[MemoryMetrics, _Mapping]] = ..., disk: _Optional[_Iterable[_Union[DiskMetrics, _Mapping]]] = ..., network: _Optional[_Union[NetworkMetrics, _Mapping]] = ..., software: _Optional[_Iterable[_Union[SoftwareInfo, _Mapping]]] = ..., docker: _Optional[_Union[_container_pb2.DockerStats, _Mapping]] = ..., k3s: _Optional[_Union[_k3s_pb2.K3sStats, _Mapping]] = ...) -> None: ...
