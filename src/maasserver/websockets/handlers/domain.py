# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The domain handler for the WebSocket connection."""

__all__ = [
    "DomainHandler",
    ]

from django.core.exceptions import ValidationError
from maasserver.enum import NODE_PERMISSION
from maasserver.forms.dnsdata import DNSDataForm
from maasserver.forms.dnsresource import DNSResourceForm
from maasserver.models import (
    DNSData,
    DNSResource,
)
from maasserver.models.domain import Domain
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
        pk = 'id'
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'delete',
            'set_active',
            'create_dnsresource',
            'update_dnsresource',
            'delete_dnsresource',
            'create_dnsdata',
            'update_dnsdata',
            'delete_dnsdata',
        ]
        listen_channels = [
            "domain",
        ]

    def dehydrate(self, domain, data, for_list=False):
        rrsets = domain.render_json_for_related_rrdata(for_list=for_list)
        if not for_list:
            data["rrsets"] = rrsets
        data["hosts"] = len({
            rr['system_id'] for rr in rrsets if rr['system_id'] is not None})
        data["resource_count"] = len(rrsets)
        if domain.is_default():
            data["displayname"] = "%s (default)" % data["name"]
        else:
            data["displayname"] = data["name"]
        return data

    def _get_domain_or_permission_error(self, params):
        domain = params.get('domain')
        if domain is None:
            raise HandlerValidationError({
                'domain': ['This field is required']
            })
        domain = self.get_object({'id': domain})
        if not self.user.has_perm(NODE_PERMISSION.ADMIN, domain):
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
            domain=domain, id=params['dnsresource'])
        form = DNSResourceForm(
            instance=dnsresource, data=params, user=self.user)
        if form.is_valid():
            form.save()
        else:
            raise ValidationError
        return self.full_dehydrate(domain)

    def delete_dnsresource(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsresource = DNSResource.objects.get(
            domain=domain, id=params['dnsresource'])
        dnsresource.delete()

    def create_dnsdata(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsresource, _ = DNSResource.objects.get_or_create(
            domain=domain, name=params['name'])
        params['dnsresource'] = dnsresource.id
        form = DNSDataForm(data=params)
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)

    def update_dnsdata(self, params):
        domain = self._get_domain_or_permission_error(params)
        dnsdata = DNSData.objects.get(
            id=params['dnsdata'], dnsresource=params['dnsresource'])
        form = DNSDataForm(data=params, instance=dnsdata)
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)
        return self.full_dehydrate(domain)

    def delete_dnsdata(self, params):
        self._get_domain_or_permission_error(params)
        dnsdata = DNSData.objects.get(id=params['dnsdata'])
        dnsdata.delete()
