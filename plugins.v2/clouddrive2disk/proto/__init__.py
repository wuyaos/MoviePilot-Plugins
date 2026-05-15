# input: none
# output: cd2_pb2, cd2_pb2_grpc modules
# pos: proto package for CloudDrive2Disk plugin; caches loaded modules in sys
#      across MoviePilot hot-reloads so AddSerializedFile is never called twice

import sys

# Use sys as a process-lifetime store — survives plugin module reloads.
_CACHE_KEY = "_clouddrive2disk_proto_cache"
if not hasattr(sys, _CACHE_KEY):
    setattr(sys, _CACHE_KEY, {})

_cache: dict = getattr(sys, _CACHE_KEY)

if "cd2_pb2" not in _cache:
    # First load: import normally and cache the module objects.
    from . import cd2_pb2  # noqa: F401
    from . import cd2_pb2_grpc  # noqa: F401
    _cache["cd2_pb2"] = cd2_pb2
    _cache["cd2_pb2_grpc"] = cd2_pb2_grpc
else:
    # Hot-reload: restore cached modules into sys.modules so that the
    # 'from . import' below finds them without re-executing the pb2 code
    # (which would call AddSerializedFile again and raise a duplicate error).
    _pkg = __name__
    sys.modules[f"{_pkg}.cd2_pb2"] = _cache["cd2_pb2"]
    sys.modules[f"{_pkg}.cd2_pb2_grpc"] = _cache["cd2_pb2_grpc"]
    from . import cd2_pb2  # noqa: F401  — resolved from sys.modules, no re-exec
    from . import cd2_pb2_grpc  # noqa: F401
