# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Monkey patch for the MAAS provisioning server"""

__all__ = [
    "add_term_error_code_to_tftp",
    "force_simplestreams_to_use_urllib2",
]

import sys


def force_simplestreams_to_use_urllib2():
    """Monkey-patch `simplestreams` to use `urllib2`.

    This prevents the use of `requests` which /may/ be helping simplestreams
    to lose file-descriptors.
    """
    import simplestreams.contentsource

    if sys.version_info > (3, 0):
        import urllib.request as urllib_request
        import urllib.error as urllib_error
    else:
        import urllib2 as urllib_request
        urllib_error = urllib_request

    vars(simplestreams.contentsource).update(
        URL_READER=simplestreams.contentsource.Urllib2UrlReader,
        URL_READER_CLASSNAME="Urllib2UrlReader", urllib_error=urllib_error,
        urllib_request=urllib_request)


def add_term_error_code_to_tftp():
    """Add error code 8 to TFT server as introduced by RFC 2347.

    Manually apply the fix to python-tx-tftp landed in
    https://github.com/shylent/python-tx-tftp/pull/20
    """
    import tftp.datagram
    if tftp.datagram.errors.get(8) is None:
        tftp.datagram.errors[8] = (
            "Terminate transfer due to option negotiation")
