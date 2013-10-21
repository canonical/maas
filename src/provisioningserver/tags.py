# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery jobs for managing tags.

"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'merge_details',
    'merge_details_cleanly',
    'MissingCredentials',
    'process_node_tags',
    ]


from collections import OrderedDict
from functools import partial
import httplib
from logging import getLogger
import urllib2

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
import bson
from lxml import etree
from provisioningserver.auth import (
    get_recorded_api_credentials,
    get_recorded_nodegroup_uuid,
    )
from provisioningserver.cluster_config import get_maas_url
from provisioningserver.utils import (
    classify,
    try_match_xpath,
    )
import simplejson as json


logger = getLogger(__name__)


class MissingCredentials(Exception):
    """The MAAS URL or credentials are not yet set."""


# An example laptop's lshw XML dump was 135kB. An example lab's LLDP
# XML dump was 1.6kB. A batch size of 100 would mean downloading ~14MB
# from the region controller, which seems workable. The previous batch
# size of 1000 would have resulted in a ~140MB download, which, on the
# face of it, appears excessive.
DEFAULT_BATCH_SIZE = 100


def get_cached_knowledge():
    """Get all the information that we need to know, or raise an error.

    :return: (client, nodegroup_uuid)
    """
    api_credentials = get_recorded_api_credentials()
    if api_credentials is None:
        logger.error("Not updating tags: don't have API key yet.")
        return None, None
    nodegroup_uuid = get_recorded_nodegroup_uuid()
    if nodegroup_uuid is None:
        logger.error("Not updating tags: don't have UUID yet.")
        return None, None
    client = MAASClient(
        MAASOAuth(*api_credentials), MAASDispatcher(),
        get_maas_url())
    return client, nodegroup_uuid


# A content-type: function mapping that can decode data of that type.
decoders = {
    "application/json": lambda data: json.loads(data),
    "application/bson": lambda data: bson.BSON(data).decode(),
}


def process_response(response):
    """All responses should be httplib.OK.

    Additionally, `decoders` will be consulted in an attempt to decode
    the content. If it can't be decoded it will be returned as bytes.

    :param response: The result of MAASClient.get/post/etc.
    :type response: urllib2.addinfourl (a file-like object that has a .code
        attribute.)
    """
    if response.code != httplib.OK:
        text_status = httplib.responses.get(response.code, '<unknown>')
        message = '%s, expected 200 OK' % text_status
        raise urllib2.HTTPError(
            response.url, response.code, message,
            response.headers, response.fp)
    content = response.read()
    content_type = response.headers.gettype()
    if content_type in decoders:
        decode = decoders[content_type]
        return decode(content)
    else:
        return content


def get_nodes_for_node_group(client, nodegroup_uuid):
    """Retrieve the UUIDs of nodes in a particular group.

    :param client: MAAS client instance
    :param nodegroup_uuid: Node group for which to retrieve nodes
    :return: List of UUIDs for nodes in nodegroup
    """
    path = '/api/1.0/nodegroups/%s/' % (nodegroup_uuid)
    return process_response(client.get(path, op='list_nodes'))


def get_details_for_nodes(client, nodegroup_uuid, system_ids):
    """Retrieve details for a set of nodes.

    :param client: MAAS client
    :param system_ids: List of UUIDs of systems for which to fetch LLDP data
    :return: Dictionary mapping node UUIDs to details, e.g. LLDP output
    """
    path = '/api/1.0/nodegroups/%s/' % (nodegroup_uuid,)
    return process_response(client.post(
        path, op='details', system_ids=system_ids))


def post_updated_nodes(client, tag_name, tag_definition, uuid, added, removed):
    """Update the nodes relevant for a particular tag.

    :param client: MAAS client
    :param tag_name: Name of tag
    :param tag_definition: Definition of the tag, used to assure that the work
        being done matches the current value.
    :param uuid: NodeGroup uuid of this worker. Needed for security
        permissions. (The nodegroup worker is only allowed to touch nodes in
        its nodegroup, otherwise you need to be a superuser.)
    :param added: Set of nodes to add
    :param removed: Set of nodes to remove
    """
    path = '/api/1.0/tags/%s/' % (tag_name,)
    logger.debug(
        "Updating nodes for %s %s, adding %s removing %s"
        % (tag_name, uuid, len(added), len(removed)))
    try:
        return process_response(client.post(
            path, op='update_nodes', as_json=True, nodegroup=uuid,
            definition=tag_definition, add=added, remove=removed))
    except urllib2.HTTPError as e:
        if e.code == httplib.CONFLICT:
            if e.fp is not None:
                msg = e.fp.read()
            else:
                msg = e.msg
            logger.info("Got a CONFLICT while updating tag: %s", msg)
            return {}
        raise


def _details_prepare_merge(details):
    # We may mutate the details later, so copy now to prevent
    # affecting the caller's data.
    details = details.copy()

    # Prepare an nsmap in an OrderedDict. This ensures that lxml
    # serializes namespace declarations in a stable order.
    nsmap = OrderedDict((ns, ns) for ns in sorted(details))

    # Root everything in a namespace-less element. Setting the nsmap
    # here ensures that prefixes are preserved when dumping later.
    # This element will be replaced by the root of the lshw detail.
    # However, if there is no lshw detail, this root element shares
    # its tag with the tag of an lshw XML tree, so that XPath
    # expressions written with the lshw tree in mind will still work
    # without it, e.g. "/list//{lldp}something".
    root = etree.Element("list", nsmap=nsmap)

    # We have copied details, and root is new.
    return details, root


def _details_make_backwards_compatible(details, root):
    # For backward-compatibilty, if lshw details are available, these
    # should form the root of the composite document.
    xmldata = details.get("lshw")
    if xmldata is not None:
        try:
            lshw = etree.fromstring(xmldata)
        except etree.XMLSyntaxError as e:
            logger.warn("Invalid lshw details: %s", e)
            del details["lshw"]  # Don't process again later.
        else:
            # We're throwing away the existing root, but we can adopt
            # its nsmap by becoming its child.
            root.append(lshw)
            root = lshw

    # We may have mutated details and root.
    return details, root


def _details_do_merge(details, root):
    # Merge the remaining details into the composite document.
    for namespace in sorted(details):
        xmldata = details[namespace]
        if xmldata is not None:
            try:
                detail = etree.fromstring(xmldata)
            except etree.XMLSyntaxError as e:
                logger.warn("Invalid %s details: %s", namespace, e)
            else:
                # Add the namespace to all unqualified elements.
                for elem in detail.iter("{}*"):
                    elem.tag = etree.QName(namespace, elem.tag)
                root.append(detail)

    # Re-home `root` in a new tree. This ensures that XPath
    # expressions like "/some-tag" work correctly. Without this, when
    # there's well-formed lshw data -- see the backward-compatibilty
    # hack futher up -- expressions would be evaluated from the first
    # root created in this function, even though that root is now the
    # parent of the current `root`.
    return etree.ElementTree(root)


def merge_details(details):
    """Merge node details into a single XML document.

    `details` should be of the form::

      {"name": xml-as-bytes, "name2": xml-as-bytes, ...}

    where `name` is the namespace (and prefix) where each detail's XML
    should be placed in the composite document; elements in each
    detail document without a namespace are moved into that namespace.

    The ``lshw`` detail is treated specially, purely for backwards
    compatibility. If present, it forms the root of the composite
    document, without any namespace changes, plus it will be included
    in the composite document in the ``lshw`` namespace.

    The returned document is always rooted with a ``list`` element.
    """
    details, root = _details_prepare_merge(details)
    details, root = _details_make_backwards_compatible(details, root)
    return _details_do_merge(details, root)


def merge_details_cleanly(details):
    """Merge node details into a single XML document.

    `details` should be of the form::

      {"name": xml-as-bytes, "name2": xml-as-bytes, ...}

    where `name` is the namespace (and prefix) where each detail's XML
    should be placed in the composite document; elements in each
    detail document without a namespace are moved into that namespace.

    This is similar to `merge_details`, but the ``lshw`` detail is not
    treated specially. The result of this function is not compatible
    with XPath expressions created for old releases of MAAS.

    The returned document is always rooted with a ``list`` element.
    """
    details, root = _details_prepare_merge(details)
    return _details_do_merge(details, root)


def gen_batch_slices(count, size):
    """Generate `slice`s to split `count` objects into batches.

    The batches will be evenly distributed; no batch will differ in
    length from any other by more than 1.

    Note that the slices returned include a step. This means that
    slicing a list with the aid of this function then concatenating
    the results will not give you the same list. All the elements will
    be present, but not in the same order.

    :return: An iterator of `slice`s.
    """
    batch_count, remaining = divmod(count, size)
    batch_count += 1 if remaining > 0 else 0
    for batch in xrange(batch_count):
        yield slice(batch, None, batch_count)


def gen_batches(things, batch_size):
    """Split `things` into even batches of <= `batch_size`.

    Note that batches are calculated by `get_batch_slices` which does
    not guarantee ordering.

    :type things: `list`, or anything else that can be sliced.

    :return: An iterator of `slice`s of `things`.
    """
    slices = gen_batch_slices(len(things), batch_size)
    return (things[s] for s in slices)


def gen_node_details(client, nodegroup_uuid, batches):
    """Fetch node details.

    This lazily fetches data in batches, but this detail is hidden
    from callers.

    :return: An iterator of ``(system-id, details-document)`` tuples.
    """
    get_details = partial(get_details_for_nodes, client, nodegroup_uuid)
    for batch in batches:
        for system_id, details in get_details(batch).iteritems():
            yield system_id, merge_details(details)


def process_all(client, tag_name, tag_definition, nodegroup_uuid, system_ids,
                xpath, batch_size=None):
    logger.debug(
        "processing %d system_ids for tag %s nodegroup %s",
        len(system_ids), tag_name, nodegroup_uuid)

    if batch_size is None:
        batch_size = DEFAULT_BATCH_SIZE

    batches = gen_batches(system_ids, batch_size)
    node_details = gen_node_details(client, nodegroup_uuid, batches)
    nodes_matched, nodes_unmatched = classify(
        partial(try_match_xpath, xpath, logger=logger), node_details)

    # Upload all updates for one nodegroup at one time. This should be no more
    # than ~41*10,000 = 410kB. That should take <1s even on a 10Mbit network.
    # This also allows us to track if a nodegroup has been processed in the DB,
    # without having to add another API call.
    post_updated_nodes(
        client, tag_name, tag_definition, nodegroup_uuid,
        nodes_matched, nodes_unmatched)


def process_node_tags(tag_name, tag_definition, tag_nsmap, batch_size=None):
    """Update the nodes for a new/changed tag definition.

    :param tag_name: Name of the tag to update nodes for
    :param tag_definition: Tag definition
    :param batch_size: Size of batch
    """
    client, nodegroup_uuid = get_cached_knowledge()
    if not all([client, nodegroup_uuid]):
        logger.error(
            "Unable to update tag: %s for definition %r. "
            "Please refresh secrets, then rebuild this tag."
            % (tag_name, tag_definition))
        raise MissingCredentials()
    # We evaluate this early, so we can fail before sending a bunch of data to
    # the server
    xpath = etree.XPath(tag_definition, namespaces=tag_nsmap)
    # Get nodes to process
    system_ids = get_nodes_for_node_group(client, nodegroup_uuid)
    process_all(
        client, tag_name, tag_definition, nodegroup_uuid, system_ids, xpath,
        batch_size=batch_size)
