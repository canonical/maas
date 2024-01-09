# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The controller handler for the WebSocket connection."""


from collections import Counter
from functools import cached_property
import logging

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import (
    BooleanField,
    ExpressionWrapper,
    OuterRef,
    Q,
    Subquery,
)

from maasserver.config import RegionConfiguration
from maasserver.exceptions import NodeActionError
from maasserver.forms import ControllerForm
from maasserver.models import Controller, Event, VLAN
from maasserver.models.controllerinfo import get_target_version
from maasserver.node_action import get_node_action
from maasserver.permissions import NodePermission
from maasserver.secrets import SecretManager
from maasserver.websockets.base import (
    dehydrate_certificate,
    HandlerError,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.node import node_prefetch, NodeHandler
from provisioningserver.certificates import Certificate

# return the list of VLAN ids connected to a controller
_vlan_ids_aggr = ArrayAgg(
    "current_config__interface__ip_addresses__subnet__vlan__id",
    distinct=True,
    filter=Q(
        current_config__interface__ip_addresses__subnet__vlan__isnull=False
    ),
)


class ControllerHandler(NodeHandler):
    class Meta(NodeHandler.Meta):
        abstract = False
        queryset = node_prefetch(
            Controller.controllers.all()
            .select_related("controllerinfo")
            .prefetch_related("service_set")
        ).annotate(vlan_ids=_vlan_ids_aggr)
        list_queryset = (
            Controller.controllers.all()
            .select_related("controllerinfo", "domain", "bmc")
            .prefetch_related("service_set")
            .prefetch_related("tags")
            .prefetch_related("ownerdata_set")
            .prefetch_related(
                "current_config__interface_set__ip_addresses__subnet__vlan"
            )
            .annotate(
                status_event_type_description=Subquery(
                    Event.objects.filter(
                        node=OuterRef("pk"), type__level__gte=logging.INFO
                    )
                    .order_by("-created", "-id")
                    .values("type__description")[:1]
                ),
                vlan_ids=_vlan_ids_aggr,
            )
        )
        allowed_methods = [
            "list",
            "get",
            "create",
            "update",
            "action",
            "set_active",
            "check_images",
            "get_summary_xml",
            "get_summary_yaml",
            "set_script_result_suppressed",
            "set_script_result_unsuppressed",
            "get_latest_failed_testing_script_results",
            "update_interface",
        ]
        form = ControllerForm
        exclude = [
            "status_expires",
            "parent",
            "boot_interface",
            "boot_cluster_ip",
            "token",
            "netboot",
            "agent_name",
            "power_state_queried",
            "power_state_updated",
            "gateway_link_ipv4",
            "gateway_link_ipv6",
            "enable_ssh",
            "skip_networking",
            "skip_storage",
            "instance_power_parameters",
            "address_ttl",
            "url",
            "dns_process",
            "managing_process",
            "current_config",
            "vault_configured",
        ]
        list_fields = [
            "id",
            "system_id",
            "hostname",
            "domain",
            "node_type",
            "status",
            "last_image_sync",
            "cpu_count",
            "cpu_speed",
            "vault_configured",
        ]
        listen_channels = ["controller"]
        create_permission = NodePermission.admin
        view_permission = NodePermission.view
        edit_permission = NodePermission.admin
        delete_permission = NodePermission.admin

    def get_form_class(self, action):
        """Return the form class used for `action`."""
        if action in ("create", "update"):
            return ControllerForm
        else:
            raise HandlerError("Unknown action: %s" % action)

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for controllers only viewable by `user`."""
        if for_list:
            qs = self._meta.list_queryset
        else:
            qs = self._meta.queryset
        return Controller.controllers.get_nodes(
            self.user, self._meta.view_permission, from_nodes=qs
        )

    def action(self, params):
        """Perform the action on the object."""
        # `get_node_action` handles the permission checking internally
        # the default view permission check is enough at this level.
        obj = self.get_object(params)
        action_name = params.get("action")
        action = get_node_action(
            obj, action_name, self.user, request=self.request
        )
        if action is None:
            raise NodeActionError(
                f"{action_name} action is not available for this node."
            )
        extra_params = params.get("extra", {})
        return action.execute(**extra_params)

    def dehydrate(self, obj, data, for_list=False):
        obj = obj.as_self()
        data = super().dehydrate(obj, data, for_list=for_list)

        vlan_counts = Counter()
        vlan_ids = [
            interface.vlan_id
            for interface in obj.current_config.interface_set.all()
            if interface.vlan_id is not None
        ]
        for vlan_id in vlan_ids:
            vlan_counts[self._vlans_ha[vlan_id]] += 1

        data.update(
            {
                "node_type_display": obj.get_node_type_display(),
                "vlans_ha": {
                    "true": vlan_counts[True],
                    "false": vlan_counts[False],
                },
                "versions": self.dehydrate_versions(obj.info),
                "service_ids": [
                    service.id for service in obj.service_set.all()
                ],
                "vault_configured": self.dehydrate_vault_flag(obj.info),
            }
        )
        if not for_list:
            data["vlan_ids"] = vlan_ids

            # include certificate info if present
            certificate = obj.get_power_parameters().get("certificate")
            key = obj.get_power_parameters().get("key")
            if certificate and key:
                cert = Certificate.from_pem(certificate, key)
                data["certificate"] = dehydrate_certificate(cert)

        return data

    def dehydrate_versions(self, info):
        if not info:
            return {}

        versions = {
            "install_type": info.install_type,
            "current": {
                "version": info.version,
            },
            "origin": info.update_origin,
            "up_to_date": info.is_up_to_date(self._target_version),
            "issues": info.get_version_issues(self._target_version),
        }
        if info.update_version:
            versions["update"] = {
                "version": info.update_version,
            }

        if info.snap_revision:
            versions["current"]["snap_revision"] = info.snap_revision
        if info.snap_cohort:
            versions["snap_cohort"] = info.snap_cohort
        if info.snap_update_revision:
            versions["update"]["snap_revision"] = info.snap_update_revision
        return versions

    def check_images(self, params):
        """Get the image sync statuses of requested controllers."""
        from maasserver import bootresources

        # FIXME alexsander-souza: we could be more precise
        if bootresources.is_import_resources_running():
            status = "Region Importing"
        else:
            status = "Synced"
        result = {}
        for node in [self.get_object(param) for param in params]:
            result[node.system_id] = status
        return result

    def dehydrate_show_os_info(self, obj):
        """Always show the OS information for controllers in the UI."""
        return True

    def dehydrate_vault_flag(self, info):
        if not info:
            return False

        return info.vault_configured

    def preprocess_form(self, action, params):
        params.update(self.preprocess_node_form(action, params))
        return super().preprocess_form(action, params)

    def register_info(self, params):
        """Return the registration info for a new controller.

        User must be a superuser to perform this action.
        """
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        secret = SecretManager().get_simple_secret("rpc-shared")
        with RegionConfiguration.open() as config:
            maas_url = config.maas_url

        return {"url": maas_url, "secret": secret}

    @cached_property
    def _vlans_ha(self):
        """Return a dict mapping VLAN IDs to their HA status."""
        return dict(
            VLAN.objects.values_list("id").annotate(
                is_ha=ExpressionWrapper(
                    Q(primary_rack__isnull=False)
                    & Q(secondary_rack__isnull=False),
                    output_field=BooleanField(),
                )
            )
        )

    @cached_property
    def _target_version(self):
        """Cache the deployment target version"""
        return get_target_version()
