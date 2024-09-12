# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.dhcp import generate_dhcp_configuration
from maasserver.models.node import RackController


class AgentConfigHandler(OperationsHandler):
    """
    AgentConfigHandler is an part of internal API that is used by MAAS Agent
    and returns configurations for various services.
    """

    api_doc_section_name = "AgentConfiguration"
    update = delete = None
    fields = ()
    hidden = True

    @classmethod
    def resource_uri(cls, system_id=None, service_name=None):
        sys_id = "system_id"
        svc_name = "service_name"
        if system_id is not None:
            sys_id = system_id
        if service_name is not None:
            svc_name = service_name
        return (
            "agent_config_handler",
            (
                sys_id,
                svc_name,
            ),
        )

    @admin_method
    def read(self, request, system_id, service_name):
        if service_name == "dhcp":
            agent = RackController.objects.get(system_id=system_id)
            config = generate_dhcp_configuration(agent)
            return config
