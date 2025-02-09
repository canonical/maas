# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views for VM hosts"""

from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404

from maasserver.models import Pod


def vmhost_certificate_handler(request, name):
    """Return the PEM content of a VM host certificate, if present."""
    vmhost = get_object_or_404(Pod, name=name)
    cert_pem = vmhost.get_power_parameters().get("certificate")
    if not cert_pem:
        return HttpResponseNotFound()
    return HttpResponse(cert_pem, content_type="text/plain")
