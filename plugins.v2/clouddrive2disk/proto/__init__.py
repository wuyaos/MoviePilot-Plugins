# input: none
# output: clouddrive2disk_pb2, clouddrive2disk_pb2_grpc modules with descriptor pool isolation
# pos: proto package for CloudDrive2Disk plugin; patches pool before import to tolerate duplicate registration

"""Descriptor pool isolation for CloudDrive2Disk proto modules.

clouddrive.proto registers under the name 'clouddrive.proto' in the global
descriptor pool. If another plugin already registered the same file (e.g. the
original clouddrivedisk / cd2disk), AddSerializedFile raises TypeError.

We patch the pool instance before importing the pb2 module so duplicate
registration is silently ignored and the existing FileDescriptor is returned.
The patch is scoped to this block and restored afterwards.
"""

from google.protobuf import descriptor_pool as _dp
from google.protobuf import descriptor_pb2 as _descriptor_pb2

_pool = _dp.Default()
_orig_add_serialized_file = _pool.AddSerializedFile


def _idempotent_add(serialized_pb: bytes):
    """Tolerate duplicate proto file registration in the descriptor pool."""
    try:
        return _orig_add_serialized_file(serialized_pb)
    except TypeError as exc:
        msg = str(exc).lower()
        if "duplicate" in msg or "already" in msg or "conflict" in msg:
            fd = _descriptor_pb2.FileDescriptorProto()
            fd.ParseFromString(serialized_pb)
            return _pool.FindFileByName(fd.name)
        raise


_pool.AddSerializedFile = _idempotent_add  # type: ignore[method-assign]

try:
    from . import clouddrive2disk_pb2  # noqa: F401, E402
    from . import clouddrive2disk_pb2_grpc  # noqa: F401, E402
finally:
    # Restore regardless of import success/failure
    _pool.AddSerializedFile = _orig_add_serialized_file  # type: ignore[method-assign]
