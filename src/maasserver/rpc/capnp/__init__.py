import os
from os import path

from provisioningserver.config import is_dev_environment


def rpc_dir(proto_file):
    if is_dev_environment():
        return path.join(path.abspath("./src/rpc"), proto_file)
    return path.join(
        os.environ.get("MAAS_DATA", "/var/lib/maas/rpc"), proto_file
    )
