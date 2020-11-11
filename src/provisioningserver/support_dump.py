# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS rack controller support dump commands."""


from functools import lru_cache
import json
import os
from pprint import pprint
import traceback

from provisioningserver.boot.tftppath import (
    get_image_metadata,
    list_boot_images,
)
from provisioningserver.config import ClusterConfiguration
from provisioningserver.utils.ipaddr import get_ip_addr
from provisioningserver.utils.iproute import get_ip_route
from provisioningserver.utils.network import get_all_interfaces_definition

all_arguments = ("--networking", "--config", "--images")


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = run.__doc__
    parser.add_argument(
        "--networking",
        action="store_true",
        required=False,
        help="Dump networking information.",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        required=False,
        help="Dump configuration information.",
    )
    parser.add_argument(
        "--images",
        action="store_true",
        required=False,
        help="Dump boot image information.",
    )


@lru_cache(1)
def get_cluster_configuration():
    config_dict = {}
    try:
        with ClusterConfiguration.open() as configuration:
            for var in vars(ClusterConfiguration):
                if not var.startswith("_"):
                    config_dict[var] = getattr(configuration, var)
    except Exception:
        print("Warning: Could not load cluster configuration.")
        print("(some data may not be accurate)")
        print()
    return config_dict


# The following lists define the functions and/or commands that will be run
# during each phase of the support dump.
NETWORKING_DUMP = [
    {"function": get_ip_addr},
    {"function": get_ip_route},
    {"function": get_all_interfaces_definition},
]

CONFIG_DUMP = [{"function": get_cluster_configuration}]

IMAGES_DUMP = [
    {"function": list_boot_images},
    {
        "title": "get_image_metadata()",
        "function": lambda *args: json.loads(get_image_metadata(*args)),
    },
]


def _dump(item, *args, **kwargs):
    if "function" in item:
        function = item["function"]
        title = item["title"] if "title" in item else function.__name__ + "()"
        print("### %s ###" % title)
        try:
            pprint(function(*args, **kwargs))
        except Exception:
            print(traceback.format_exc())
        print()
    if "command" in item:
        print("### %s ###" % item["command"])
        os.system("%s 2>&1" % item["command"])
        print()


def run(args):
    """Dump support information. By default, dumps everything available."""
    params = vars(args).copy()
    networking = params.pop("networking", False)
    config = params.pop("config", False)
    images = params.pop("images", False)

    config_dict = get_cluster_configuration()

    complete = False
    if not networking and not images and not config:
        complete = True

    if complete or networking:
        for item in NETWORKING_DUMP:
            _dump(item)

    if complete or config:
        for item in CONFIG_DUMP:
            _dump(item)

    if complete or images:
        for item in IMAGES_DUMP:
            _dump(item, config_dict["tftp_root"])
