# input: none
# output: clouddrive2disk_pb2, clouddrive2disk_pb2_grpc modules
# pos: proto package for CloudDrive2Disk plugin; clouddrive2disk.proto uses package clouddrive2disk
#      so the descriptor pool name is unique and never conflicts with other plugins

from . import clouddrive2disk_pb2  # noqa: F401
from . import clouddrive2disk_pb2_grpc  # noqa: F401
