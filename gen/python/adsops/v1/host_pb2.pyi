import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HostRecord(_message.Message):
    __slots__ = ("id", "resource_name", "hostname", "type", "provider", "region", "status", "environment", "owners", "mail_groups", "metadata", "average_daily_cost", "average_monthly_cost", "external_id", "external_url", "created_at", "updated_at", "children")
    ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_NAME_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    OWNERS_FIELD_NUMBER: _ClassVar[int]
    MAIL_GROUPS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_DAILY_COST_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_MONTHLY_COST_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_ID_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_URL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    id: int
    resource_name: str
    hostname: str
    type: str
    provider: str
    region: str
    status: str
    environment: str
    owners: _containers.RepeatedScalarFieldContainer[str]
    mail_groups: _containers.RepeatedScalarFieldContainer[str]
    metadata: _struct_pb2.Struct
    average_daily_cost: float
    average_monthly_cost: float
    external_id: str
    external_url: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    children: _containers.RepeatedCompositeFieldContainer[HostRecord]
    def __init__(self, id: _Optional[int] = ..., resource_name: _Optional[str] = ..., hostname: _Optional[str] = ..., type: _Optional[str] = ..., provider: _Optional[str] = ..., region: _Optional[str] = ..., status: _Optional[str] = ..., environment: _Optional[str] = ..., owners: _Optional[_Iterable[str]] = ..., mail_groups: _Optional[_Iterable[str]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., average_daily_cost: _Optional[float] = ..., average_monthly_cost: _Optional[float] = ..., external_id: _Optional[str] = ..., external_url: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., children: _Optional[_Iterable[_Union[HostRecord, _Mapping]]] = ...) -> None: ...
