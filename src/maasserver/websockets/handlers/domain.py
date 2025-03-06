# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The domain handler for the WebSocket connection."""

from django.core.exceptions import ValidationError

from maasserver.forms.dnsdata import DNSDataForm
from maasserver.forms.dnsresource import DNSResourceForm
from maasserver.forms.domain import DomainForm
from maasserver.models import DNSData, DNSResource, GlobalDefault
from maasserver.models.domain import Domain
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.permissions import NodePermission
from maasserver.sqlalchemy import service_layer
from maasserver.websockets.base import (
    AdminOnlyMixin,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class DomainHandler(TimestampedModelHandler, AdminOnlyMixin):
    class Meta:
        queryset = Domain.objects.all()
        pk = "id"
        form = DomainForm
        form_requires_request = False
        allowed_methods = [
            "list",
            "get",
            "create",
            "update",
            "delete",
            "set_active",
            "set_default",
            "create_dnsresource",
            "update_dnsresource",
            "delete_dnsresource",
            "create_address_record",
            "update_address_record",
            "delete_address_record",
            "create_dnsdata",
            "update_dnsdata",
            "delete_dnsdata",
        ]
        listen_channels = ["domain"]

    def dehydrate(self, domain, data, for_list=False):
        rrsets = service_layer.services.domains.render_json_for_related_rrdata(
            domain_id=domain.id, user_id=self.user.id
        )
        if not for_list:
            data["rrsets"] = rrsets
        data["hosts"] = len(
            {rr["system_id"] for rr in rrsets if rr["system_id"] is not None}
        )
        data["resource_count"] = len(rrsets)
        if domain.is_default():
            data["displayname"] = "%s (default)" % data["name"]
            data["is_default"] = True
        else:
            data["displayname"] = data["name"]
            data["is_default"] = False
        return data

    def _get_domain_or_permission_error(self, params):
        domain = params.get("domain")
        if domain is None:
            raise HandlerValidationError(
                {"domain": ["This field is required"]}
            )
        domain = self.get_object({"id": domain})
        if not self.user.has_perm(NodePermission.admin, domain):
            raise HandlerPermissionError()
        return domain

    def create_dnsresource(self, params):
        self._get_domain_or_permission_error(params)
        form = DNSResourceForm(data=params, user=self.user)
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)

    def update_dnsresource(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsresource = DNSResource.objects.get(
            domain=domain, id=params["dnsresource_id"]
        )
        form = DNSResourceForm(
            instance=dnsresource, data=params, user=self.user
        )
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)
        return self.full_dehydrate(domain)

    def delete_dnsresource(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsresource = DNSResource.objects.get(
            domain=domain, id=params["dnsresource_id"]
        )
        dnsresource.delete()

    def create_address_record(self, params):
        domain = self._get_domain_or_permission_error(params)
        if params["ip_addresses"] == [""]:
            raise ValidationError(
                "Data field is required when creating an %s record."
                % params["rrtype"]
            )
        dnsresource, created = DNSResource.objects.get_or_create(
            domain=domain, name=params["name"]
        )
        if created:
            ip_addresses = []
        else:
            ip_addresses = dnsresource.get_addresses()
        ip_addresses.extend(params["ip_addresses"])
        params["ip_addresses"] = " ".join(ip_addresses)
        form = DNSResourceForm(
            data=params, user=self.user, instance=dnsresource
        )
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)

    def update_address_record(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsresource, created = DNSResource.objects.get_or_create(
            domain=domain, name=params["name"]
        )
        if created:
            # If we ended up creating a record, that's because the name
            # was changed, so we'll start with an empty list. But that also
            # means we need to edit the record with the original name.
            ip_addresses = []
            previous_dnsresource = DNSResource.objects.get(
                domain=domain, name=params["previous_name"]
            )
            prevoius_ip_addresses = previous_dnsresource.get_addresses()
            prevoius_ip_addresses.remove(params["previous_rrdata"])
            modified_addresses = " ".join(prevoius_ip_addresses)
            form = DNSResourceForm(
                data=dict(ip_addresses=modified_addresses),
                user=self.user,
                instance=previous_dnsresource,
            )
            if form.is_valid():
                form.save()
            else:
                raise ValidationError(form.errors)
        else:
            ip_addresses = dnsresource.get_addresses()
            # Remove the previous address for the record being edited.
            # The previous_rrdata field will contain the original value
            # for the IP address in the edited row.
            ip_addresses.remove(params["previous_rrdata"])
            # remove the IP if necessary
            ip = StaticIPAddress.objects.get(ip=params["previous_rrdata"])
            if ip.is_safe_to_delete():
                ip.delete()
        ip_addresses.extend(params["ip_addresses"])
        params["ip_addresses"] = " ".join(ip_addresses)
        form = DNSResourceForm(
            data=params, user=self.user, instance=dnsresource
        )
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)

    def delete_address_record(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsresource = DNSResource.objects.get(
            domain=domain, id=params["dnsresource_id"]
        )
        ip_addresses = dnsresource.get_addresses()
        ip_addresses.remove(params["rrdata"])
        # remove the IP if necessary
        ip = StaticIPAddress.objects.get(ip=params["rrdata"])
        if ip.is_safe_to_delete():
            ip.delete()
        params["ip_addresses"] = " ".join(ip_addresses)
        form = DNSResourceForm(
            data=params, user=self.user, instance=dnsresource
        )
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)

    def create_dnsdata(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsresource, _ = DNSResource.objects.get_or_create(
            domain=domain, name=params["name"]
        )
        params["dnsresource"] = dnsresource.id
        form = DNSDataForm(data=params)
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)

    def update_dnsdata(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsdata = DNSData.objects.get(
            id=params["dnsdata_id"], dnsresource_id=params["dnsresource_id"]
        )
        form = DNSDataForm(data=params, instance=dnsdata)
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)
        return self.full_dehydrate(domain)

    def delete_dnsdata(self, params):
        self._get_domain_or_permission_error(params)
        dnsdata = DNSData.objects.get(id=params["dnsdata_id"])
        dnsdata.delete()

    def set_default(self, params):
        domain = self._get_domain_or_permission_error(params)
        global_defaults = GlobalDefault.objects.instance()
        global_defaults.domain = domain
        global_defaults.save()
        return self.full_dehydrate(domain)
