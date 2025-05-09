#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import dataclasses

# Workflows names
MSM_ENROL_SITE_WORKFLOW_NAME = "msm-enrol-site"
MSM_TOKEN_REFRESH_WORKFLOW_NAME = "msm-token-refresh"
MSM_HEARTBEAT_WORKFLOW_NAME = "msm-heartbeat"
MSM_WITHDRAW_WORKFLOW_NAME = "msm-withdraw"


# Workflows parameters
@dataclasses.dataclass
class MSMEnrolParam:
    site_name: str
    site_url: str
    url: str
    jwt: str
    cluster_uuid: str
    metainfo: str | None = None


@dataclasses.dataclass
class MSMConnectorParam:
    url: str
    jwt: str
    rotation_interval_minutes: int = 0


@dataclasses.dataclass
class MachinesCountByStatus:
    """Machine counts by status."""

    allocated: int = 0
    deployed: int = 0
    ready: int = 0
    error: int = 0
    other: int = 0


@dataclasses.dataclass
class MSMHeartbeatParam:
    sm_url: str
    jwt: str
    site_name: str
    site_url: str
    rotation_interval_minutes: int
    status: MachinesCountByStatus | None = None


@dataclasses.dataclass
class MSMTokenRefreshParam:
    sm_url: str
    jwt: str
    rotation_interval_minutes: int


@dataclasses.dataclass
class MSMSetBootSourceParam:
    sm_url: str
