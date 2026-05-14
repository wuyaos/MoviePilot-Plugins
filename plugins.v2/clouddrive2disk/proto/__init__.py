# input: none
# output: cd2_pb2, cd2_pb2_grpc modules
# pos: proto package for CloudDrive2Disk plugin; patches descriptor pool before
#      import to tolerate MoviePilot hot-reloads (same Python process, pool persists)

from google.protobuf import descriptor_pool as _dp


def _patch_pool_for_hot_reload() -> None:
    """
    MoviePilot reloads plugin modules inside the same Python interpreter.
    The global protobuf descriptor pool retains all previously registered entries,
    so on a second load AddSerializedFile raises 'duplicate file name' or
    'duplicate extension entry'.  We patch it once to return the already-registered
    FileDescriptor instead of raising, making the import idempotent.
    """
    pool = _dp.Default()
    # Avoid double-wrapping across multiple reloads of this module.
    if getattr(pool, "_cd2disk_patched", False):
        return
    orig = pool.AddSerializedFile

    def _tolerant(serialized: bytes):
        try:
            return orig(serialized)
        except TypeError as exc:
            if "duplicate" not in str(exc).lower():
                raise
            # File or extension already registered — return the existing descriptor.
            try:
                from google.protobuf import descriptor_pb2 as _dpb2
                fd_proto = _dpb2.FileDescriptorProto()
                fd_proto.ParseFromString(serialized)
                return pool.FindFileByName(fd_proto.name)
            except Exception:
                pass   # Can't retrieve — swallow so imports don't crash MP

    try:
        pool.AddSerializedFile = _tolerant
        pool._cd2disk_patched = True
    except (AttributeError, TypeError):
        pass  # Read-only C extension slot; skip patch, hope pool is clean


_patch_pool_for_hot_reload()

from . import cd2_pb2  # noqa: F401
from . import cd2_pb2_grpc  # noqa: F401
