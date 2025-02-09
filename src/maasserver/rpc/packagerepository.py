# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to configuration settings."""

from urllib.parse import urlparse

from maasserver.models.packagerepository import PackageRepository
from maasserver.utils.orm import transactional
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def get_archive_mirrors():
    """Obtain the Main and Ports archive mirror to use by clusters.

    Returns them as a structure suitable for returning in the response
    for :py:class:`~provisioningserver.rpc.region.GetArchiveMirrors`.
    """
    main_archive = PackageRepository.get_main_archive_url()
    ports_archive = PackageRepository.get_ports_archive_url()
    if main_archive is not None:
        main_archive = urlparse(main_archive)
    if ports_archive is not None:
        ports_archive = urlparse(ports_archive)
    return {"main": main_archive, "ports": ports_archive}
