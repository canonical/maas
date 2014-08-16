# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `LicenseKey`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'LicenseKeyHandler',
    'LicenseKeysHandler',
    ]


from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.forms import LicenseKeyForm
from maasserver.models import LicenseKey
from maasserver.utils.orm import get_one
from piston.utils import rc


class LicenseKeysHandler(OperationsHandler):
    """Manage the license keys."""
    api_doc_section_name = "License Keys"

    update = delete = None

    def read(self, request):
        """List license keys."""
        return LicenseKey.objects.all().order_by('osystem', 'distro_series')

    def create(self, request):
        """Define a license key.

        :param osystem: Operating system that the key belongs to.
        :param distro_series: OS release that the key belongs to.
        :param license_key: License key for osystem/distro_series combo.
        """
        # If the user provides no parametes to the create command, then
        # django will make the request.data=None. This will cause the form
        # to be valid, not returning all the missing fields.
        data = request.data
        if data is None:
            data = {}
        form = LicenseKeyForm(data=data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        return form.save()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('license_keys_handler', [])


class LicenseKeyHandler(OperationsHandler):
    """Manage a license key."""
    api_doc_section_name = "License Key"

    model = LicenseKey
    fields = ('osystem', 'distro_series', 'license_key')

    # Creation happens on the LicenseKeysHandler.
    create = None

    def read(self, request, osystem, distro_series):
        """Read license key."""
        return get_object_or_404(
            LicenseKey, osystem=osystem, distro_series=distro_series)

    def update(self, request, osystem, distro_series):
        """Update license key.

        :param osystem: Operating system that the key belongs to.
        :param distro_series: OS release that the key belongs to.
        :param license_key: License key for osystem/distro_series combo.
        """
        license_key = get_object_or_404(
            LicenseKey, osystem=osystem, distro_series=distro_series)
        data = request.data
        if data is None:
            data = {}
        form = LicenseKeyForm(instance=license_key, data=data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        return form.save()

    def delete(self, request, osystem, distro_series):
        """Delete license key."""
        license_key = get_one(
            LicenseKey.objects.filter(
                osystem=osystem, distro_series=distro_series))
        if license_key is not None:
            license_key.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, license_key=None):
        # See the comment in NodeHandler.resource_uri.
        if license_key is None:
            osystem = 'osystem'
            distro_series = 'distro_series'
        else:
            osystem = license_key.osystem
            distro_series = license_key.distro_series
        return ('license_key_handler', (osystem, distro_series))
