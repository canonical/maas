#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

# Workflows names
CONFIGURE_AGENT_WORKFLOW_NAME = "configure-agent"

# Defined in maasagent
CONFIGURE_CLUSTER_SERVICE_WORKFLOW_NAME = "configure-cluster-service"
CONFIGURE_POWER_SERVICE_WORKFLOW_NAME = "configure-power-service"
CONFIGURE_HTTPPROXY_SERVICE_WORKFLOW_NAME = "configure-httpproxy-service"
CONFIGURE_DHCP_SERVICE_WORKFLOW_NAME = "configure-dhcp-service"
CONFIGURE_RESOLVER_SERVICE_WORKFLOW_NAME = "configure-resolver-service"


# Workflows parameters
@dataclass
class ConfigureAgentParam:
    system_id: str


@dataclass
class ConfigureClusterServiceParam:
    pass


@dataclass
class ConfigureDHCPServiceParam:
    enabled: bool
