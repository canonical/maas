# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Change cluster controller configuration settings.
"""


import argparse
from uuid import uuid4

from formencode.api import Invalid
from formencode.validators import StringBool

from provisioningserver.config import ClusterConfiguration, UUID_NOT_SET


def update_maas_cluster_conf(
    urls=None, uuid=None, init=None, tftp_port=None, tftp_root=None, debug=None
):
    """This function handles the logic behind using the parameters passed to
    run and setting / initializing values in the config backend.

    :param urls: The MAAS URLs to set. Does nothing if None.
    :param tftp_port: The tftp port number to set. Does nothing if None.
    :param tftp_root: The tftp root file path to set. Does nothing if None.
    :param uuid: The UUID to use for this cluster. Does nothing if None.
    :param init: Initializes the config backend with a new UUID if
    the backend does not currently have a value configured.
    NOTE: that the argument parser will not let uuid
    and init be passed at the same time, as these are mutually exclusive
    parameters.
    :param debug: Enables or disables debug mode.
    """
    with ClusterConfiguration.open_for_update() as config:
        if urls is not None:
            config.maas_url = urls
        if uuid is not None:
            config.cluster_uuid = uuid
        if init:
            cur_uuid = config.cluster_uuid
            if cur_uuid == UUID_NOT_SET:
                config.cluster_uuid = str(uuid4())
        if tftp_port is not None:
            config.tftp_port = tftp_port
        if tftp_root is not None:
            config.tftp_root = tftp_root
        if debug is not None:
            config.debug = debug


all_arguments = (
    "--region-url",
    "--uuid",
    "--init",
    "--tftp-port",
    "--tftp-root",
    "--debug",
)


def to(cast_type):
    """Convert the value to python."""

    def _inner(value):
        try:
            return cast_type().to_python(value)
        except Invalid as exc:
            raise argparse.ArgumentTypeError(str(exc))

    return _inner


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.add_argument(
        "--region-url",
        action="append",
        required=False,
        help=(
            "Change the URL where cluster controllers can reach the MAAS "
            "region controller. Use parameter multiple times to connect to "
            "multiple region controllers."
        ),
    )
    uuid_group = parser.add_mutually_exclusive_group()
    uuid_group.add_argument(
        "--uuid",
        action="store",
        required=False,
        help=(
            "Change the cluster UUID. Use --init instead to generate a "
            "new UUID if one is not already set."
        ),
    )
    uuid_group.add_argument(
        "--init",
        action="store_true",
        required=False,
        help="Generate a new UUID for this cluster controller.",
    )
    parser.add_argument(
        "--tftp-port",
        action="store",
        required=False,
        help="The root directory for TFTP resources.",
    )
    parser.add_argument(
        "--tftp-root",
        action="store",
        required=False,
        help="The root directory for TFTP resources.",
    )
    parser.add_argument(
        "--debug",
        action="store",
        type=to(StringBool),
        required=False,
        help="Enable or disable debug mode.",
    )


def run(args):
    """Update configuration settings."""
    params = vars(args).copy()
    urls = params.pop("region_url", None)
    uuid = params.pop("uuid", None)
    init = params.pop("init", None)
    tftp_port = params.pop("tftp_port", None)
    tftp_root = params.pop("tftp_root", None)
    debug = params.pop("debug", None)

    update_maas_cluster_conf(urls, uuid, init, tftp_port, tftp_root, debug)
