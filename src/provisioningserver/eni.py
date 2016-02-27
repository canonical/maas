# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Get /etc/network/interface definition for the rack controller."""

__all__ = [
    "get_interfaces_definition",
    "clear_current_interfaces_definition",
]

from provisioningserver.utils.network import get_eni_interfaces_definition

# Holds the current /etc/network/interfaces definition that the rack
# controller has processed.
_current_eni_definition = None


def get_interfaces_definition():
    """Return tuple containing the /etc/network/interfaces definition and a
    boolean for it the definition has changed since the last time this method
    was called.
    """
    global _current_eni_definition
    if _current_eni_definition is None:
        _current_eni_definition = get_eni_interfaces_definition()
        return _current_eni_definition, True
    else:
        new_definition = get_eni_interfaces_definition()
        if _current_eni_definition != new_definition:
            _current_eni_definition = new_definition
            return _current_eni_definition, True
        else:
            return _current_eni_definition, False


def clear_current_interfaces_definition():
    """Clear the current cached interfaces definition."""
    global _current_eni_definition
    _current_eni_definition = None
