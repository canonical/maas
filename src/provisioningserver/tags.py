# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cluster-side evaluation of tags."""


from collections import OrderedDict
from functools import partial
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request

import bson
from lxml import etree

from apiclient.maas_client import MAASClient
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.utils import classify
from provisioningserver.utils.xpath import try_match_xpath

log = LegacyLogger()
maaslog = get_maas_logger("tag_processing")


# An example laptop's lshw XML dump was 135kB. An example lab's LLDP
# XML dump was 1.6kB. A batch size of 100 would mean downloading ~14MB
# from the region controller, which seems workable. The previous batch
# size of 1000 would have resulted in a ~140MB download, which, on the
# face of it, appears excessive.
DEFAULT_BATCH_SIZE = 100


def process_response(response):
    """All responses should be httplib.OK.

    The response should contain a BSON document (content-type
    application/bson) or a JSON document (content-type application/json). If
    so, the document will be decoded and the result returned, otherwise the
    raw binary content will be returned.

    :param response: The result of MAASClient.get/post/etc.
    :type response: urllib.request.addinfourl (a file-like object that has a
        .code attribute.)

    """
    if response.code != http.client.OK:
        text_status = http.client.responses.get(response.code, "<unknown>")
        message = "%s, expected 200 OK" % text_status
        raise urllib.error.HTTPError(
            response.url, response.code, message, response.headers, response.fp
        )
    content = response.read()
    content_type = response.headers.get_content_type()
    if content_type == "application/bson":
        return bson.BSON(content).decode()
    elif content_type == "application/json":
        content_charset = response.headers.get_content_charset()
        return json.loads(
            content.decode(
                "utf-8" if content_charset is None else content_charset
            )
        )
    else:
        return content


def get_details_for_nodes(
    client: MAASClient, system_ids: list[str]
) -> dict[str, bytes]:
    """Retrieve details for a set of nodes.

    :param client: MAAS client
    :param system_ids: List of UUIDs of systems for which to fetch LLDP data
    :return: Dictionary mapping node UUIDs to details, e.g. LLDP output
    """
    details = {}
    for system_id in system_ids:
        path = "/MAAS/api/2.0/nodes/%s/" % system_id
        data = process_response(client.get(path, op="details"))
        details[system_id] = data
    return details


def post_updated_nodes(
    client: MAASClient, rack_id, tag_name, tag_definition, added, removed
):
    """Update the nodes relevant for a particular tag.

    :param client: MAAS client
    :param rack_id: System ID for rack controller
    :param tag_name: Name of tag
    :param tag_definition: Definition of the tag, used to assure that the work
        being done matches the current value.
    :param added: Set of nodes to add
    :param removed: Set of nodes to remove
    """
    path = f"/MAAS/api/2.0/tags/{tag_name}/"
    log.debug(
        "Updating nodes for {name}, adding {adding} removing {removing}",
        name=tag_name,
        adding=added,
        removing=removed,
    )
    try:
        return process_response(
            client.post(
                path,
                op="update_nodes",
                as_json=True,
                rack_controller=rack_id,
                definition=tag_definition,
                add=added,
                remove=removed,
            )
        )
    except urllib.error.HTTPError as e:
        if e.code == http.client.CONFLICT:
            if e.fp is not None:
                msg = e.fp.read()
            else:
                msg = e.msg
            maaslog.info("Got a CONFLICT while updating tag: %s", msg)
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
            maaslog.warning("Invalid lshw details: %s", e)
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
                maaslog.warning("Invalid %s details: %s", namespace, e)
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
    for batch in range(batch_count):
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


def gen_node_details(client: MAASClient, batches):
    """Fetch node details.

    This lazily fetches data in batches, but this detail is hidden
    from callers.

    :return: An iterator of ``(system-id, details-document)`` tuples.
    """
    get_details = partial(get_details_for_nodes, client)
    for batch in batches:
        for system_id, details in get_details(batch).items():
            yield system_id, merge_details(details)


def process_all(
    client: MAASClient,
    rack_id,
    tag_name,
    tag_definition,
    system_ids,
    xpath,
    batch_size=None,
):
    log.debug(
        "Processing {nums} system_ids for tag {name}.",
        nums=len(system_ids),
        name=tag_name,
    )

    if batch_size is None:
        batch_size = DEFAULT_BATCH_SIZE

    batches = gen_batches(system_ids, batch_size)
    node_details = gen_node_details(client, batches)
    nodes_matched, nodes_unmatched = classify(
        partial(try_match_xpath, xpath, logger=maaslog), node_details
    )
    post_updated_nodes(
        client,
        rack_id,
        tag_name,
        tag_definition,
        nodes_matched,
        nodes_unmatched,
    )


def process_node_tags(
    rack_id,
    nodes,
    tag_name,
    tag_definition,
    tag_nsmap,
    client: MAASClient,
    batch_size=None,
):
    """Update the nodes for a new/changed tag definition.

    :param rack_id: System ID for the rack controller.
    :param nodes: List of nodes to process tags for.
    :param tag_name: Name of the tag to update nodes for
    :param tag_definition: Tag definition
    :param tag_nsmap: The namespace map as used by LXML's ETree library.
    :param client: A `MAASClient` used to fetch the node's details via
        calls to the web API.
    :param batch_size: Size of batch
    """
    # We evaluate this early, so we can fail before sending a bunch of data to
    # the server
    xpath = etree.XPath(tag_definition, namespaces=tag_nsmap)
    system_ids = [node["system_id"] for node in nodes]
    process_all(
        client,
        rack_id,
        tag_name,
        tag_definition,
        system_ids,
        xpath,
        batch_size=batch_size,
    )
