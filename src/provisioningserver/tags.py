# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery jobs for managing tags.

"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'MissingCredentials',
    'process_node_tags',
    ]


import httplib
import simplejson as json
from lxml import etree

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )

from provisioningserver.auth import (
    get_recorded_api_credentials,
    get_recorded_maas_url,
    get_recorded_nodegroup_uuid,
    )

from provisioningserver.logging import task_logger


class MissingCredentials(Exception):
    """The MAAS URL or credentials are not yet set."""


DEFAULT_BATCH_SIZE = 100


def get_cached_knowledge():
    """Get all the information that we need to know, or raise an error.

    :return: (client, nodegroup_uuid)
    """
    maas_url = get_recorded_maas_url()
    if maas_url is None:
        task_logger.error("Not updating tags: don't have API URL yet.")
        return None, None
    api_credentials = get_recorded_api_credentials()
    if api_credentials is None:
        task_logger.error("Not updating tags: don't have API key yet.")
        return None, None
    nodegroup_uuid = get_recorded_nodegroup_uuid()
    if nodegroup_uuid is None:
        task_logger.error("Not updating tags: don't have UUID yet.")
        return None, None
    client = MAASClient(MAASOAuth(*api_credentials), MAASDispatcher(),
        maas_url)
    return client, nodegroup_uuid


def process_response(response):
    """All responses should be httplib.OK and contain JSON content.

    :param response: The result of MAASClient.get/post/etc.
    :type response: urllib2.addinfourl (a file-like object that has a .code
        attribute.)
    """
    if response.code != httplib.OK:
        text_status = httplib.responses.get(response.code, '<unknown>')
        raise AssertionError('Unexpected HTTP status: %s %s, expected 200 OK'
            % (response.code, text_status))
    return json.loads(response.read())


def get_nodes_for_node_group(client, nodegroup_uuid):
    """Retrieve the UUIDs of nodes in a particular group.

    :param client: MAAS client instance
    :param nodegroup_uuid: Node group for which to retrieve nodes
    :return: List of UUIDs for nodes in nodegroup
    """
    path = '/api/1.0/nodegroups/%s/' % (nodegroup_uuid)
    return process_response(client.get(path, op='list_nodes'))


def get_hardware_details_for_nodes(client, nodegroup_uuid, system_ids):
    """Retrieve the lshw output for a set of nodes.

    :param client: MAAS client
    :param system_ids: List of UUIDs of systems for which to fetch lshw data
    :return: Dictionary mapping node UUIDs to lshw output
    """
    path = '/api/1.0/nodegroups/%s/' % (nodegroup_uuid,)
    return process_response(client.post(
        path, op='node_hardware_details', as_json=True, system_ids=system_ids))


def post_updated_nodes(client, tag_name, uuid, added, removed):
    """Update the nodes relevant for a particular tag.

    :param client: MAAS client
    :param tag_name: Name of tag
    :param uuid: NodeGroup uuid of this worker. Needed for security
        permissions. (The nodegroup worker is only allowed to touch nodes in
        its nodegroup, otherwise you need to be a superuser.)
    :param added: Set of nodes to add
    :param removed: Set of nodes to remove
    """
    path = '/api/1.0/tags/%s/' % (tag_name,)
    task_logger.debug('Updating nodes for %s %s, adding %s removing %s'
        % (tag_name, uuid, len(added), len(removed)))
    return process_response(client.post(
        path, op='update_nodes', as_json=True,
        nodegroup=uuid, add=added, remove=removed))


def process_batch(xpath, hardware_details):
    """Get the details for one batch, and process whether they match or not.
    """
    # Fetch node XML in batches
    matched_nodes = []
    unmatched_nodes = []
    for system_id, hw_xml in hardware_details:
        matched = False
        if hw_xml is not None:
            try:
                xml = etree.XML(hw_xml)
            except etree.XMLSyntaxError as e:
                task_logger.debug('Invalid hardware_details for %s: %s'
                    % (system_id, e))
            else:
                if xpath(xml):
                    matched = True
        if matched:
            matched_nodes.append(system_id)
        else:
            unmatched_nodes.append(system_id)
    return matched_nodes, unmatched_nodes


def process_all(client, tag_name, nodegroup_uuid, system_ids, xpath,
                batch_size=None):
    if batch_size is None:
        batch_size = DEFAULT_BATCH_SIZE
    all_matched = []
    all_unmatched = []
    task_logger.debug('processing %d system_ids for tag %s nodegroup %s'
                      % (len(system_ids), tag_name, nodegroup_uuid))
    for i in range(0, len(system_ids), batch_size):
        selected_ids = system_ids[i:i + batch_size]
        details = get_hardware_details_for_nodes(
            client, nodegroup_uuid, selected_ids)
        matched, unmatched = process_batch(xpath, details)
        task_logger.debug(
            'processing batch of %d ids received %d details'
            ' (%d matched, %d unmatched)'
            % (len(selected_ids), len(details), len(matched), len(unmatched)))
        all_matched.extend(matched)
        all_unmatched.extend(unmatched)
    # Upload all updates for one nodegroup at one time. This should be no more
    # than ~41*10,000 = 410kB. That should take <1s even on a 10Mbit network.
    # This also allows us to track if a nodegroup has been processed in the DB,
    # without having to add another API call.
    post_updated_nodes(
        client, tag_name, nodegroup_uuid, all_matched, all_unmatched)


def process_node_tags(tag_name, tag_definition, batch_size=None):
    """Update the nodes for a new/changed tag definition.

    :param tag_name: Name of the tag to update nodes for
    :param tag_definition: Tag definition
    :param batch_size: Size of batch
    """
    client, nodegroup_uuid = get_cached_knowledge()
    if not all([client, nodegroup_uuid]):
        task_logger.error('Unable to update tag: %s for definition %r'
            ' please refresh secrets, then rebuild this tag'
            % (tag_name, tag_definition))
        raise MissingCredentials()
    # We evaluate this early, so we can fail before sending a bunch of data to
    # the server
    xpath = etree.XPath(tag_definition)
    # Get nodes to process
    system_ids = get_nodes_for_node_group(client, nodegroup_uuid)
    process_all(client, tag_name, nodegroup_uuid, system_ids, xpath,
                batch_size=batch_size)
