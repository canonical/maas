# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin for the MAAS Region daemon."""

__all__ = []


try:
    from maasserver.plugin import RegionServiceMaker
except ImportError:
    pass  # Ignore.
else:
    # Construct objects which *provide* the relevant interfaces. The name of
    # these variables is irrelevant, as long as there are *some* names bound
    # to providers of IPlugin and IServiceMaker.
    service = RegionServiceMaker(
        "maas-regiond", "The MAAS Region Controller daemon.")
