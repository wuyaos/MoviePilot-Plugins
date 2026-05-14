# input: none
# output: cd2_pb2, cd2_pb2_grpc modules
# pos: proto package for CloudDrive2Disk plugin; cd2.proto uses package cd2
#      so the descriptor pool name is unique and never conflicts with other plugins

from . import cd2_pb2  # noqa: F401
from . import cd2_pb2_grpc  # noqa: F401
