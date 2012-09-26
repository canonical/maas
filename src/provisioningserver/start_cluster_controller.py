# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command: start the cluster controller."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'add_arguments',
    'run',
    ]

import httplib
import json
import os
from subprocess import Popen
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
from provisioningserver.logging import task_logger


class ClusterControllerRejected(Exception):
    """Request to become a cluster controller has been rejected."""


def add_arguments(parser):
    """For use by :class:`MainScript`."""
    parser.add_argument(
        'server_url', metavar='URL', help="URL to the MAAS region controller.")


def log_error(exception):
    task_logger.info(
        "Could not register with region controller: %s."
        % exception.reason)


def make_anonymous_api_client(server_url):
    """Create an unauthenticated API client."""
    return MAASClient(NoAuth(), MAASDispatcher(), server_url)


def register(server_url):
    """Request Rabbit connection details from the domain controller.

    Offers this machine to the region controller as a potential cluster
    controller.

    :return: A dict of connection details if this cluster controller has been
        accepted, or `None` if there is no definite response yet.  If there
        is no definite response, retry this call later.
    :raise ClusterControllerRejected: if this system has been rejected as a
        cluster controller.
    """
    known_responses = {httplib.OK, httplib.FORBIDDEN, httplib.ACCEPTED}
    client = make_anonymous_api_client(server_url)
    try:
        response = client.post('api/1.0/nodegroups/', 'register')
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


def start_celery(connection_details):
    broker_url = connection_details['BROKER_URL']

    # XXX JeroenVermeulen 2012-09-24, bug=1055523: Fill in proper
    # cluster-specific queue name once we have those (based on cluster
    # uuid).
    queue = 'celery'

    # Copy environment, but also tell celeryd what broker to listen to.
    env = dict(os.environ, CELERY_BROKER_URL=broker_url)

    queues = [
        'common',
        'update_dhcp_queue',
        queue,
        ]
    command = [
        'celeryd',
        '--logfile=/var/log/maas/celery.log',
        '--loglevel=INFO',
        '--beat',
        '-Q', ','.join(queues),
        ]
    Popen(command, env=env)


def request_refresh(server_url):
    client = make_anonymous_api_client(server_url)
    try:
        client.post('api/1.0/nodegroups/', 'refresh_workers')
    except URLError as e:
        task_logger.warn(
            "Could not request secrets from region controller: %s"
            % e.reason)


def start_up(server_url, connection_details):
    """We've been accepted as a cluster controller; start doing the job.

    This starts up celeryd, listening to the broker that the region
    controller pointed us to, and on the appropriate queue.
    """
    start_celery(connection_details)
    sleep(10)
    request_refresh(server_url)


def run(args):
    """Start the cluster controller.

    If this system is still awaiting approval as a cluster controller, this
    command will keep looping until it gets a definite answer.
    """
    connection_details = register(args.server_url)
    while connection_details is None:
        sleep(60)
        connection_details = register(args.server_url)
    start_up(args.server_url, connection_details)
