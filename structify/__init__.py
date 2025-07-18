from __future__ import annotations

import struct
from typing import Dict, IO, List, Optional, Type, Union

INT8_T = 'b'
UINT8_T = 'B'
INT16_T = 'h'
UINT16_T = 'H'
INT32_T = 'i'
UINT32_T = 'I'
INT64_T = 'q'
UINT64_T = 'Q'
CHAR = 's'
FLOAT32_T = 'f'
FLOAT64_T = 'd'

BYTE_ORDER_NATIVE = '@'
BYTE_ORDER_NATIVE_STD = '='
BYTE_ORDER_LITTLE_ENDIAN = '<'
BYTE_ORDER_BIG_ENDIAN = '>'
BYTE_ORDER_NETWORK = '!'

DEFAULT_BYTE_ORDER = BYTE_ORDER_LITTLE_ENDIAN

FieldValueType = Union[int, float, str]


class StructException(Exception):
    pass


class StructField:
    # used to track ordering of fields within a struct
    count_: int = 0

    def __init__(self, field_type, default: Optional[FieldValueType] = None,
                 str_len: Optional[int] = None):
        if field_type == CHAR and not str_len:
            raise StructException('CHAR fields are fixed width and require '
                                  'strlen to be specified')
        self.field_type: str = field_type
        self.default: Optional[FieldValueType] = default
        self.str_len: int = str_len
        # record count of this instance
        self.count: int = StructField.count_
        StructField.count_ += 1
        self.index: int = 0  # set by MetaStruct for each instance
        # stores the name of the attribute that this field is connected to
        # will be set by __set_name__ during class creation
        self.name = ''  # type: str

    # descriptor interface
    def __get__(self, instance: Struct, owner):
        if not instance:
            return self
        return instance.get_field_value(self.name)

    def __set__(self, instance: Struct, value):
        instance.set_field_value(self.name, value)

    def __set_name__(self, owner, name: str):
        self.name = name


def int8_t(default: int = None) -> StructField:
    return StructField(INT8_T, default=default)


def uint8_t(default: int = None) -> StructField:
    return StructField(UINT8_T, default=default)


def int16_t(default: int = None) -> StructField:
    return StructField(INT16_T, default=default)


def uint16_t(default: int = None) -> StructField:
    return StructField(UINT16_T, default=default)


def int32_t(default: int = None) -> StructField:
    return StructField(INT32_T, default=default)


def uint32_t(default: int = None) -> StructField:
    return StructField(UINT32_T, default=default)


def int64_t(default: int = None) -> StructField:
    return StructField(INT64_T, default=default)


def uint64_t(default: int = None) -> StructField:
    return StructField(UINT64_T, default=default)


def float32_t(default: float = None) -> StructField:
    return StructField(FLOAT32_T, default=default)


def float64_t(default: float = None) -> StructField:
    return StructField(FLOAT64_T, default=default)


def char(strlen: int, default: str = None) -> StructField:
    return StructField(CHAR, default=default, str_len=strlen)


class MetaStruct(type):
    def __new__(mcs, name, bases, attrs):
        new_class: Type[Struct] = super().__new__(mcs, name, bases, attrs)

        # Walk through the MRO to find all StructField instances
        struct_fields = {}
        for base in reversed(new_class.__mro__):
            for attr, value in base.__dict__.items():
                if isinstance(value, StructField):
                    struct_fields[attr] = value

        new_class._DEFAULT_VALUES = []
        new_class._NAME_INDEX_MAP = {}

        # sort the fields in declaration order
        field_list = sorted(struct_fields.values(), key=lambda f: f.count)
        # calculate the format and field map
        fmt = ''
        field: StructField
        for index, field in enumerate(field_list):
            field_type = field.field_type
            if field_type == CHAR:
                fmt += str(field.str_len)
            fmt += field_type
            field.index = index
            new_class._NAME_INDEX_MAP[field.name] = index
            new_class._DEFAULT_VALUES.append(field.default)

        new_class._BASE_STRUCT_FORMAT = fmt
        new_class._STRUCT_FORMAT = getattr(
            new_class, 'BYTE_ORDER', DEFAULT_BYTE_ORDER
        ) + fmt
        new_class._PACKER = struct.Struct(new_class._STRUCT_FORMAT)

        return new_class


class Struct(metaclass=MetaStruct):
    # Child classes can override this to set preferred byte order
    BYTE_ORDER = DEFAULT_BYTE_ORDER

    # Private class vars, will be overridden by metaclass
    _BASE_STRUCT_FORMAT = ''
    _STRUCT_FORMAT = ''
    _NAME_INDEX_MAP: Dict[str, int] = {}
    _DEFAULT_VALUES: List = []
    _PACKER: struct.Struct = struct.Struct(_STRUCT_FORMAT)

    def __init__(self, **kwargs):
        # initialise values list to defaults
        self.values: list = self._DEFAULT_VALUES.copy()

        if kwargs:
            # initialise any values passed in via kwargs
            for name, index in self._NAME_INDEX_MAP.items():
                if name in kwargs:
                    self.values[index] = kwargs.pop(name)

            if kwargs:
                raise StructException(f'Unexpected kwargs {kwargs}')

    def get_field_value(self, name: str):
        return self.values[self._NAME_INDEX_MAP[name]]

    def set_field_value(self, name: str, value):
        self.values[self._NAME_INDEX_MAP[name]] = value

    def pack(self) -> bytes:
        return self._PACKER.pack(*self.values)

    def pack_endian(self, byte_order: str) -> bytes:
        return struct.pack(byte_order + self._BASE_STRUCT_FORMAT, *self.values)

    def unpack(self, bytes_: bytes):
        self.values = self._PACKER.unpack(bytes_)

    def unpack_endian(self, bytes_: bytes, byte_order: str):
        self.values = struct.unpack(byte_order + self._BASE_STRUCT_FORMAT,
                                    bytes_)

    def __len__(self):
        return self._PACKER.size

    def sizeof(self):
        return self.__len__()


class FileHelper:
    def __init__(self, fp):
        if 'b' not in fp.mode:
            raise StructException('File must be opened in binary mode')
        self.fp: IO = fp

    def read_into(self, struct_obj: Struct):
        size = struct_obj.sizeof()
        bytes_: bytes = self.fp.read(size)
        if len(bytes_) < size:
            return False
        struct_obj.unpack(bytes_)
        return True

    def write(self, struct_obj: Struct):
        return self.fp.write(struct_obj.pack())
