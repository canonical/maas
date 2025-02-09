# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `LicenseKey`."""

from django.shortcuts import get_object_or_404
from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import LicenseKeyForm
from maasserver.models import LicenseKey
from maasserver.utils.orm import get_one


class LicenseKeysHandler(OperationsHandler):
    """Manage the license keys."""

    api_doc_section_name = "License Keys"

    update = delete = None

    def read(self, request):
        """@description-title List license keys
        @description List all available license keys.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        available license keys.
        @success-example "success-json" [exkey=license-keys-placeholder]
        placeholder text
        """
        return LicenseKey.objects.all().order_by("osystem", "distro_series")

    def create(self, request):
        """@description-title Define a license key
        @description Define a license key.

        @param (string) "osystem" [required=true] Operating system that the key
        belongs to.

        @param (string) "distro_series" [required=true] OS release that the key
        belongs to.

        @param (string) "license_key" [required=true] License key for
        osystem/distro_series combo.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new license
        key.
        @success-example "success-json" [exkey=license-keys-placeholder]
        placeholder text
        """
        # If the user provides no parametes to the create command, then
        # django will make the request.data=None. This will cause the form
        # to be valid, not returning all the missing fields.
        if request.data is None:
            data = {}
        else:
            data = request.data.copy()

        if "distro_series" in data:
            # Preprocess distro_series if present.
            if "/" in data["distro_series"]:
                if "osystem" not in data:
                    # Construct osystem value from distroseries.
                    data["osystem"] = data["distro_series"].split("/", 1)[0]
            else:
                # If distro_series is not of the form "os/series", we combine
                # osystem with distro_series since that is what LicenseKeyForm
                # expects.
                if "osystem" in data:
                    data["distro_series"] = "{}/{}".format(
                        data["osystem"],
                        data["distro_series"],
                    )
        form = LicenseKeyForm(data=data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        return form.save()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("license_keys_handler", [])


class LicenseKeyHandler(OperationsHandler):
    """Manage a license key."""

    api_doc_section_name = "License Key"

    model = LicenseKey
    fields = ("osystem", "distro_series", "license_key")

    # Creation happens on the LicenseKeysHandler.
    create = None

    def read(self, request, osystem, distro_series):
        """@description-title Read license key
        @description Read a license key for the given operating sytem and
        distro series.

        @param (string) "{osystem}" [required=true] Operating system that the
        key belongs to.

        @param (string) "{distro_series}" [required=true] OS release that the
        key belongs to.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        license key.
        @success-example "success-json" [exkey=license-keys-placeholder]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested operating system and distro
        series combination is not found.
        @error-example "not-found"
            Unknown API endpoint: /MAAS/api/2.0/license-key/windows/win2012/.
        """
        return get_object_or_404(
            LicenseKey, osystem=osystem, distro_series=distro_series
        )

    def update(self, request, osystem, distro_series):
        """@description-title Update license key
        @description Update a license key for the given operating system and
        distro series.

        @param (string) "{osystem}" [required=true] Operating system that the
        key belongs to.

        @param (string) "{distro_series}" [required=true] OS release that the
        key belongs to.

        @param (string) "license_key" [required=false] License key for
        osystem/distro_series combo.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        license key.
        @success-example "success-json" [exkey=license-keys-placeholder]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested operating system and distro
        series combination is not found.
        @error-example "not-found"
            Unknown API endpoint: /MAAS/api/2.0/license-key/windows/win2012/.
        """
        license_key = get_object_or_404(
            LicenseKey, osystem=osystem, distro_series=distro_series
        )
        data = request.data
        if data is None:
            data = {}
        form = LicenseKeyForm(instance=license_key, data=data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        return form.save()

    def delete(self, request, osystem, distro_series):
        """@description-title Delete license key
        @description Delete license key for the given operation system and
        distro series.

        @param (string) "{osystem}" [required=true] Operating system that the
        key belongs to.

        @param (string) "{distro_series}" [required=true] OS release that the
        key belongs to.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested operating system and distro
        series combination is not found.
        @error-example "not-found"
            Unknown API endpoint: /MAAS/api/2.0/license-key/windows/win2012/.
        """
        license_key = get_one(
            LicenseKey.objects.filter(
                osystem=osystem, distro_series=distro_series
            )
        )
        if license_key is not None:
            license_key.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, license_key=None):
        # See the comment in NodeHandler.resource_uri.
        if license_key is None:
            osystem = "osystem"
            distro_series = "distro_series"
        else:
            osystem = license_key.osystem
            distro_series = license_key.distro_series
        return ("license_key_handler", (osystem, distro_series))
