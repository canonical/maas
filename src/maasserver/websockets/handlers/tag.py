# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest

from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT, NODE_TYPE
from maasserver.forms import TagForm
from maasserver.models.tag import Tag
from maasserver.node_constraint_filter_forms import FreeTextFilterNodeForm
from maasserver.websockets.base import AdminOnlyMixin, HandlerValidationError
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.events import EVENT_TYPES


def _annotate_qs_with_counts(qs: QuerySet) -> QuerySet:
    """Helper to add annotations for node type."""
    return qs.annotate(
        machine_count=Count(
            "node", filter=Q(node__node_type=NODE_TYPE.MACHINE)
        ),
        device_count=Count("node", filter=Q(node__node_type=NODE_TYPE.DEVICE)),
        controller_count=Count(
            "node",
            filter=Q(
                node__node_type__in=(
                    NODE_TYPE.RACK_CONTROLLER,
                    NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                )
            ),
        ),
    )


class TagHandler(TimestampedModelHandler, AdminOnlyMixin):
    class Meta:
        form = TagForm
        form_requires_request = False
        queryset = _annotate_qs_with_counts(Tag.objects).all()
        pk = "id"
        allowed_methods = [
            "list",
            "get",
            "create",
            "update",
            "delete",
        ]
        listen_channels = ["tag"]

    def _create(self, params):
        obj = super()._create(params)
        # add fields matching annotations from queryset to the object, since it
        # doesn't come from the DB
        for field in ("machine_count", "device_count", "controller_count"):
            setattr(obj, field, 0)
        self._create_audit_event(f"Tag '{obj.name}' created.")
        return obj

    def _delete(self, obj):
        self._create_audit_event(f"Tag '{obj.name}' deleted.")
        return super()._delete(obj)

    def _update(self, obj, params):
        name = obj.name
        obj = super()._update(obj, params)

        new_name = params.get("name")
        action = f"renamed to '{new_name}'" if new_name else "updated"
        self._create_audit_event(f"Tag '{name}' {action}.")
        return obj

    def dehydrate(self, obj, data, for_list=False):
        for field in ("machine_count", "device_count", "controller_count"):
            data[field] = getattr(obj, field)
        return data

    def _create_audit_event(self, description):
        request = HttpRequest()
        request.user = self.user
        create_audit_event(
            EVENT_TYPES.TAG,
            ENDPOINT.UI,
            request,
            None,
            description=description,
        )

    def _node_filter(self, params):
        form = FreeTextFilterNodeForm(data=params)
        if not form.is_valid():
            raise HandlerValidationError(form.errors)
        mh = MachineHandler(self.user, self.cache, self.request)
        qs = mh.get_queryset(for_list=True).filter(tags__isnull=False)
        qs, _, _ = form.filter_nodes(qs)
        return qs.values_list("id", flat=True)

    def list(self, params):
        """List objects."""
        if "node_filter" in params:
            node_ids = self._node_filter(params["node_filter"])
            qs_tags = _annotate_qs_with_counts(
                Tag.objects.filter(node__id__in=node_ids)
            ).all()
            return self._build_list_simple(qs_tags, params)
        else:
            return super().list(params)
