# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Monkey patch for the MAAS provisioning server"""

__all__ = [
    "add_term_error_code_to_tftp",
]


def add_term_error_code_to_tftp():
    """Add error code 8 to TFT server as introduced by RFC 2347.

    Manually apply the fix to python-tx-tftp landed in
    https://github.com/shylent/python-tx-tftp/pull/20
    """
    import tftp.datagram
    if tftp.datagram.errors.get(8) is None:
        tftp.datagram.errors[8] = (
            "Terminate transfer due to option negotiation")
