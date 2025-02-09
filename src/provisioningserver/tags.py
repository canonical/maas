# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cluster-side evaluation of tags."""

from collections import OrderedDict

from lxml import etree

from provisioningserver.logger import get_maas_logger, LegacyLogger

log = LegacyLogger()
maaslog = get_maas_logger("tag_processing")


# An example laptop's lshw XML dump was 135kB. An example lab's LLDP
# XML dump was 1.6kB. A batch size of 100 would mean downloading ~14MB
# from the region controller, which seems workable. The previous batch
# size of 1000 would have resulted in a ~140MB download, which, on the
# face of it, appears excessive.
DEFAULT_BATCH_SIZE = 100


def _details_prepare_merge(
    details: dict[str, bytes],
) -> tuple[dict[str, bytes], etree._Element]:
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


def _details_make_backwards_compatible(
    details: dict[str, bytes], root: etree._Element
) -> tuple[dict[str, bytes], etree._Element]:
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


def _details_do_merge(
    details: dict[str, bytes], root: etree._Element
) -> etree._Element:
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


def merge_details(details: dict[str, bytes]) -> etree._Element:
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


def merge_details_cleanly(details: dict[str, bytes]) -> etree._Element:
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
