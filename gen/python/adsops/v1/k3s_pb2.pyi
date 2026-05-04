import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class NodeInfo(_message.Message):
    __slots__ = ("name", "role", "status", "version")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    role: str
    status: str
    version: str
    def __init__(self, name: _Optional[str] = ..., role: _Optional[str] = ..., status: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class NamespaceInfo(_message.Message):
    __slots__ = ("name", "total_pods", "running_pods")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TOTAL_PODS_FIELD_NUMBER: _ClassVar[int]
    RUNNING_PODS_FIELD_NUMBER: _ClassVar[int]
    name: str
    total_pods: int
    running_pods: int
    def __init__(self, name: _Optional[str] = ..., total_pods: _Optional[int] = ..., running_pods: _Optional[int] = ...) -> None: ...

class K3sStats(_message.Message):
    __slots__ = ("timestamp", "available", "node_name", "total_nodes", "ready_nodes", "total_pods", "running_pods", "failed_pods", "nodes", "namespaces")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    NODE_NAME_FIELD_NUMBER: _ClassVar[int]
    TOTAL_NODES_FIELD_NUMBER: _ClassVar[int]
    READY_NODES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_PODS_FIELD_NUMBER: _ClassVar[int]
    RUNNING_PODS_FIELD_NUMBER: _ClassVar[int]
    FAILED_PODS_FIELD_NUMBER: _ClassVar[int]
    NODES_FIELD_NUMBER: _ClassVar[int]
    NAMESPACES_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    available: bool
    node_name: str
    total_nodes: int
    ready_nodes: int
    total_pods: int
    running_pods: int
    failed_pods: int
    nodes: _containers.RepeatedCompositeFieldContainer[NodeInfo]
    namespaces: _containers.RepeatedCompositeFieldContainer[NamespaceInfo]
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., available: _Optional[bool] = ..., node_name: _Optional[str] = ..., total_nodes: _Optional[int] = ..., ready_nodes: _Optional[int] = ..., total_pods: _Optional[int] = ..., running_pods: _Optional[int] = ..., failed_pods: _Optional[int] = ..., nodes: _Optional[_Iterable[_Union[NodeInfo, _Mapping]]] = ..., namespaces: _Optional[_Iterable[_Union[NamespaceInfo, _Mapping]]] = ...) -> None: ...
