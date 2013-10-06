# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Facilities to obtain probed details for nodes.

For example, hardware information as reported by ``lshw`` and network
topology information derived from LLDP.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "get_probed_details",
    "get_single_probed_details",
    "script_output_nsmap",
]

from base64 import b64decode
from collections import Sequence

from metadataserver.models import (
    commissioningscript,
    NodeCommissionResult,
    )

# A map of commissioning script output names to their detail
# namespaces. These namespaces are used in the return values from
# get_single_probed_details() and get_probed_details(), and in the
# composite XML document that's used when evaluating tag expressions.
script_output_nsmap = {
    commissioningscript.LLDP_OUTPUT_NAME: "lldp",
    commissioningscript.LSHW_OUTPUT_NAME: "lshw",
}


def get_single_probed_details(system_id):
    """Return details of the node identified by `system_id`.

    Currently this consists of the node's ``lshw`` XML dump and an
    LLDP XML capture done during commissioning, but may be
    extended in the future.

    :return: A `dict` of the form ``{"lshw": b"<.../>", "lldp":
        b"<.../>"}``, where values are byte strings of XML.
    """
    assert isinstance(system_id, unicode)
    probe_details = get_probed_details((system_id,))
    return probe_details[system_id]


def get_probed_details(system_ids):
    """Return details of the nodes identified by `system_ids`.

    :return: A ``{system_id: {...details...}, ...}`` map, where the
        inner dictionaries have the same form as those returned by
        `get_single_probed_details`.
    """
    assert not isinstance(system_ids, (bytes, unicode))

    if not isinstance(system_ids, Sequence):
        system_ids = list(system_ids)

    assert not any(isinstance(system_id, bytes) for system_id in system_ids)

    query = NodeCommissionResult.objects.filter(
        node__system_id__in=system_ids, name__in=script_output_nsmap,
        script_result=0)
    results = query.values_list('node__system_id', 'name', 'data')

    detail_template = dict.fromkeys(script_output_nsmap.values())
    details = {
        system_id: detail_template.copy()
        for system_id in system_ids
    }
    for system_id, script_output_name, b64data in results:
        namespace = script_output_nsmap[script_output_name]
        details[system_id][namespace] = b64decode(b64data)

    return details
