# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin for the MAAS Region daemon."""

__all__ = []


try:
    from maasserver.plugin import (
        RegionAllInOneServiceMaker,
        RegionMasterServiceMaker,
        RegionWorkerServiceMaker,
    )
except ImportError:
    pass  # Ignore.
else:
    # Construct objects which *provide* the relevant interfaces. The name of
    # these variables is irrelevant, as long as there are *some* names bound
    # to providers of IPlugin and IServiceMaker.
    master = RegionMasterServiceMaker(
        "maas-regiond-master", "The MAAS Region Controller master process.")
    worker = RegionWorkerServiceMaker(
        "maas-regiond-worker", "The MAAS Region Controller worker process.")
    all_in_one = RegionAllInOneServiceMaker(
        "maas-regiond-all", "The MAAS Region Controller all-in-one process.")
