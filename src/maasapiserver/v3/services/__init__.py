from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.services.bmc import BmcService
from maasapiserver.v3.services.nodes import NodesService
from maasapiserver.v3.services.vmcluster import VmClustersService
from maasapiserver.v3.services.zones import ZonesService


class ServiceCollectionV3:
    """Provide all v3 services."""

    def __init__(self, connection: AsyncConnection):
        self.nodes = NodesService(connection=connection)
        self.vmclusters = VmClustersService(connection=connection)
        self.bmc = BmcService(connection=connection)
        self.zones = ZonesService(
            connection=connection,
            nodes_service=self.nodes,
            vmcluster_service=self.vmclusters,
            bmc_service=self.bmc,
        )
