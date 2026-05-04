import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ContainerStats(_message.Message):
    __slots__ = ("id", "name", "image", "state", "cpu_pct", "mem_used_bytes", "mem_limit_bytes", "mem_pct", "rx_bytes_per_sec", "tx_bytes_per_sec", "restart_count")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    CPU_PCT_FIELD_NUMBER: _ClassVar[int]
    MEM_USED_BYTES_FIELD_NUMBER: _ClassVar[int]
    MEM_LIMIT_BYTES_FIELD_NUMBER: _ClassVar[int]
    MEM_PCT_FIELD_NUMBER: _ClassVar[int]
    RX_BYTES_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    TX_BYTES_PER_SEC_FIELD_NUMBER: _ClassVar[int]
    RESTART_COUNT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    image: str
    state: str
    cpu_pct: float
    mem_used_bytes: int
    mem_limit_bytes: int
    mem_pct: float
    rx_bytes_per_sec: float
    tx_bytes_per_sec: float
    restart_count: int
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., image: _Optional[str] = ..., state: _Optional[str] = ..., cpu_pct: _Optional[float] = ..., mem_used_bytes: _Optional[int] = ..., mem_limit_bytes: _Optional[int] = ..., mem_pct: _Optional[float] = ..., rx_bytes_per_sec: _Optional[float] = ..., tx_bytes_per_sec: _Optional[float] = ..., restart_count: _Optional[int] = ...) -> None: ...

class DockerStats(_message.Message):
    __slots__ = ("timestamp", "available", "total_containers", "running_containers", "containers")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_CONTAINERS_FIELD_NUMBER: _ClassVar[int]
    RUNNING_CONTAINERS_FIELD_NUMBER: _ClassVar[int]
    CONTAINERS_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    available: bool
    total_containers: int
    running_containers: int
    containers: _containers.RepeatedCompositeFieldContainer[ContainerStats]
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., available: _Optional[bool] = ..., total_containers: _Optional[int] = ..., running_containers: _Optional[int] = ..., containers: _Optional[_Iterable[_Union[ContainerStats, _Mapping]]] = ...) -> None: ...
