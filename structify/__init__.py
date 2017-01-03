from __future__ import absolute_import, unicode_literals

import struct


INT8_T = 'b'
UINT8_T = 'B'
INT16_T = 'h'
UINT16_T = 'H'
INT32_T = 'i'
UINT32_T = 'I'
INT64_T = 'q'
UINT64_T = 'Q'
CHAR = 's'

BYTE_ORDER_NATIVE = '@'
BYTE_ORDER_NATIVE_STD = '='
BYTE_ORDER_LITTLE_ENDIAN = '<'
BYTE_ORDER_BIG_ENDIAN = '>'
BYTE_ORDER_NETWORK = '!'

DEFAULT_BYTE_ORDER = BYTE_ORDER_NETWORK

ERROR_MSG = 'StructFields can only be used within Struct objects'


class StructException(Exception):
    pass


class StructField(object):
    # used to track ordering of fields within a struct
    count_ = 0  # type: int

    def __init__(self, byte_size, default=None, strlen=None):
        if byte_size == CHAR and not strlen:
            raise StructException('CHAR fields are fixed width and require '
                                  'strlen to be specified')
        self.byte_size = byte_size  # type: str
        self.default = default  # type: any
        self.strlen = strlen  # type: int
        self.count = StructField.count_  # type: int
        StructField.count_ += 1
        # stores the name of the attribute that this field is connected to
        # will be set by MetaStruct during Struct creation
        self.name = None  # type: str

    # descriptor interface
    def __get__(self, instance, owner):
        if not self.name:
            raise RuntimeError(ERROR_MSG)
        return getattr(instance.data_, self.name, self.default)

    def __set__(self, instance, value):
        if not self.name:
            raise RuntimeError(ERROR_MSG)
        setattr(instance.data_, self.name, value)


class StructBase(object):
    pass


def recurse_struct_fields(cls, fields):
    for name, field in cls.__dict__.items():
        if isinstance(field, StructField):
            field.name = name
            fields.append(field)
    for base in cls.__bases__:
        if issubclass(base, StructBase):
            recurse_struct_fields(base, fields)


class MetaStruct(type):
    def __init__(cls, name, bases, dct):
        fields = []  # type: List[StructField]
        recurse_struct_fields(cls, fields)

        if fields:
            fields = sorted(fields, key=lambda f: f.count)

            if 'byte_order' in dct:
                byte_order = cls.byte_order
            else:
                byte_order = DEFAULT_BYTE_ORDER

            # calculate the format
            fmt = ''
            for field in fields:  # type: StructField
                byte_size = field.byte_size
                if byte_size == CHAR:
                    fmt += str(field.strlen)
                fmt += byte_size

            base_fmt = fmt
            fmt = byte_order + fmt
            
            class StructData(object):
                __slots__ = [field.name for field in fields]
                packer = struct.Struct(fmt)
    
                def pack(self):
                    values = [getattr(self, f.name) for f in fields]
                    return self.packer.pack(*values)
    
                def pack_endian(self, byte_order_):
                    values = [getattr(self, f.name) for f in fields]
                    return struct.pack(byte_order_+base_fmt, *values)
    
                def unpack_values_(self, values):
                    index = 0
                    for f in fields:
                        setattr(self, f.name, values[index])
                        index += 1
    
                def unpack(self, string):
                    values = self.packer.unpack(string)
                    self.unpack_values_(values)
    
                def unpack_endian(self, string, byte_order_):
                    values = struct.unpack(byte_order_+base_fmt, string)
                    self.unpack_values_(values)

            # This will be the __init__ function for the class we are creating
            def init(obj, **kwargs):
                # ensure that the struct data object is created
                obj.data_ = StructData()

                # init values from kwargs if supplied
                for f in fields:
                    fname = f.name
                    if fname in kwargs:
                        setattr(obj, fname, kwargs.pop(fname))
                if kwargs:
                    raise StructException(
                        'Unexpected kwargs passed to {}: {}'.format(
                            name, kwargs
                        )
                    )

            # override the __init__ for the Struct subclass
            cls.__init__ = init

        super(MetaStruct, cls).__init__(name, bases, dct)


class Struct(StructBase):
    __metaclass__ = MetaStruct

    def __init__(self, **kwargs):
        pass

    def pack(self):
        return self.data_.pack()

    def pack_endian(self, byte_order):
        return self.data_.pack_endian(byte_order)

    def unpack(self, string):
        self.data_.unpack(string)

    def unpack_endian(self, string, byte_order):
        self.data_.unpack_endian(string, byte_order)

    def __len__(self):
        return self.data_.packer.size

    def sizeof(self):
        return self.__len__()


class FileHelper(object):
    def __init__(self, fp):
        if 'b' not in fp.mode:
            raise StructException('File must be opened in binary mode')
        self.fp = fp  # type: file

    def read_into(self, struct_obj):
        size = struct_obj.sizeof()
        string = self.fp.read(size)
        struct_obj.unpack(string)

    def write(self, struct_obj):
        return self.fp.write(struct_obj.pack())


def int8_t(default=None):
    return StructField(INT8_T, default=default)


def uint8_t(default=None):
    return StructField(UINT8_T, default=default)


def int16_t(default=None):
    return StructField(INT16_T, default=default)


def uint16_t(default=None):
    return StructField(UINT16_T, default=default)


def int32_t(default=None):
    return StructField(INT32_T, default=default)


def uint32_t(default=None):
    return StructField(UINT32_T, default=default)


def int64_t(default=None):
    return StructField(INT64_T, default=default)


def uint64_t(default=None):
    return StructField(UINT64_T, default=default)


def char(strlen, default=None):
    return StructField(CHAR, default=default, strlen=strlen)


class TestStruct(Struct):
    a = uint8_t()
    b = int64_t(34)


class SubTestStruct(TestStruct):
    c = int8_t()


class AnotherStruct(Struct):
    byte_order = '>'
    x = int8_t()
    y = uint64_t(8989)
