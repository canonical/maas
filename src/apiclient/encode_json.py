# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Encoding requests as JSON data."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'encode_json_data',
    ]

import json


def encode_json_data(params):
    """Encode params as JSON and set up headers for an HTTP POST.

    :param params: Can be a dict or a list, but should generally be a dict, to
    match the key-value data expected by most receiving APIs.
    :return: (body, headers)
    """
    body = json.dumps(params)
    headers = {
        'Content-Length': unicode(len(body)),
        'Content-Type': 'application/json',
        }
    return body, headers
