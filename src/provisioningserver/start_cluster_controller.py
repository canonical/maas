# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command: start the cluster controller."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'add_arguments',
    'run',
    ]

import httplib
import json
from time import sleep
from urllib2 import (
    HTTPError,
    URLError,
    )

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    NoAuth,
    )
from provisioningserver.cluster_config import get_cluster_uuid
from provisioningserver.logger import get_maas_logger
from provisioningserver.network import discover_networks


maaslog = get_maas_logger("cluster")


class ClusterControllerRejected(Exception):
    """Request to become a cluster controller has been rejected."""


def add_arguments(parser):
    """For use by :class:`MainScript`."""
    parser.add_argument(
        'server_url', metavar='URL', help="URL to the MAAS region controller.")


def log_error(exception):
    maaslog.info(
        "Could not register with region controller: %s."
        % exception.reason)


def make_anonymous_api_client(server_url):
    """Create an unauthenticated API client."""
    return MAASClient(NoAuth(), MAASDispatcher(), server_url)


def register(server_url):
    """Register with the region controller.

    Offers this machine to the region controller as a potential cluster
    controller.

    :param server_url: URL to the region controller's MAAS API.
    :return: A dict of connection details if this cluster controller has been
        accepted, or `None` if there is no definite response yet.  If there
        is no definite response, retry this call later.
    :raise ClusterControllerRejected: if this system has been rejected as a
        cluster controller.
    """
    known_responses = {httplib.OK, httplib.FORBIDDEN, httplib.ACCEPTED}

    interfaces = json.dumps(discover_networks())
    client = make_anonymous_api_client(server_url)
    cluster_uuid = get_cluster_uuid()
    try:
        response = client.post(
            'api/1.0/nodegroups/', 'register',
            interfaces=interfaces, uuid=cluster_uuid)
    except HTTPError as e:
        status_code = e.code
        if e.code not in known_responses:
            log_error(e)
            # Unknown error.  Keep trying.
            return None
    except URLError as e:
        log_error(e)
        # Unknown error.  Keep trying.
        return None
    else:
        status_code = response.getcode()

    if status_code == httplib.OK:
        # Our application has been approved.  Proceed.
        return json.loads(response.read())
    elif status_code == httplib.ACCEPTED:
        # Our application is still waiting for approval.  Keep trying.
        return None
    elif status_code == httplib.FORBIDDEN:
        # Our application has been rejected.  Give up.
        raise ClusterControllerRejected(
            "This system has been rejected as a cluster controller.")
    else:
        raise AssertionError("Unexpected return code: %r" % status_code)


def run(args):
    """Start the cluster controller.

    If this system is still awaiting approval as a cluster controller, this
    command will keep looping until it gets a definite answer.
    """
    maaslog.info("Starting cluster controller %s." % get_cluster_uuid())
    connection_details = register(args.server_url)
    while connection_details is None:
        sleep(60)
        connection_details = register(args.server_url)
