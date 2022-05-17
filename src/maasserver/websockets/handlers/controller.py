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
from maasserver.models import Config, Controller, Event, RackController, VLAN
from maasserver.models.controllerinfo import get_target_version
from maasserver.node_action import compile_node_actions
from maasserver.permissions import NodePermission
from maasserver.websockets.base import HandlerError, HandlerPermissionError
from maasserver.websockets.handlers.node import node_prefetch, NodeHandler

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
                status_event_description=Subquery(
                    Event.objects.filter(
                        node=OuterRef("pk"), type__level__gte=logging.INFO
                    )
                    .order_by("-created", "-id")
                    .values("description")[:1]
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
            "check_power",
            "check_images",
            "create_physical",
            "create_vlan",
            "create_bond",
            "update_interface",
            "delete_interface",
            "link_subnet",
            "unlink_subnet",
            "get_summary_xml",
            "get_summary_yaml",
            "set_script_result_suppressed",
            "set_script_result_unsuppressed",
            "get_latest_failed_testing_script_results",
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
        # `compile_node_actions` handles the permission checking internally
        # the default view permission check is enough at this level.
        obj = self.get_object(params)
        action_name = params.get("action")
        actions = compile_node_actions(obj, self.user, request=self.request)
        action = actions.get(action_name)
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
        for vlan_id in obj.vlan_ids:
            vlan_counts[self._vlans_ha[vlan_id]] += 1

        data.update(
            {
                "vlans_ha": {
                    "true": vlan_counts[True],
                    "false": vlan_counts[False],
                },
                "versions": self.dehydrate_versions(obj.info),
                "service_ids": [
                    service.id for service in obj.service_set.all()
                ],
            }
        )
        if not for_list:
            data["vlan_ids"] = [
                interface.vlan_id
                for interface in obj.current_config.interface_set.all()
            ]
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
        result = {}
        for node in [self.get_object(param) for param in params]:
            # We use a RackController method; without the cast, it's a Node.
            node = node.as_rack_controller()
            if isinstance(node, RackController):
                result[node.system_id] = (
                    node.get_image_sync_status().replace("-", " ").title()
                )
        return result

    def dehydrate_show_os_info(self, obj):
        """Always show the OS information for controllers in the UI."""
        return True

    def preprocess_form(self, action, params):
        params.update(self.preprocess_node_form(action, params))
        return super().preprocess_form(action, params)

    def register_info(self, params):
        """Return the registration info for a new controller.

        User must be a superuser to perform this action.
        """
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        rpc_shared_secret = Config.objects.get_config("rpc_shared_secret")
        with RegionConfiguration.open() as config:
            maas_url = config.maas_url

        return {"url": maas_url, "secret": rpc_shared_secret}

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
