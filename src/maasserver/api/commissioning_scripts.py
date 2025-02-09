# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `CommissioningScript`."""

from base64 import b64encode

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from piston3.utils import rc

from maasserver.api.scripts import NodeScriptHandler, NodeScriptsHandler
from maasserver.api.support import deprecated, OperationsHandler
from maasserver.api.utils import get_mandatory_param
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.script import ScriptForm
from maasserver.models import Script
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.fields import Bin
from provisioningserver.events import EVENT_TYPES


def get_content_parameter(request):
    """Get the "content" parameter from a CommissioningScript POST or PUT."""
    content_file = get_mandatory_param(request.FILES, "content")
    return content_file.read()


@deprecated(use=NodeScriptsHandler)
class CommissioningScriptsHandler(OperationsHandler):
    """
    Manage custom commissioning scripts.

    This functionality is only available to administrators.
    """

    api_doc_section_name = "Commissioning scripts"

    update = delete = None

    def read(self, request):
        """List commissioning scripts."""
        return sorted(
            script.name
            for script in Script.objects.filter(
                script_type=SCRIPT_TYPE.COMMISSIONING
            )
        )

    def create(self, request):
        """Create a new commissioning script.

        Each commissioning script is identified by a unique name.

        By convention the name should consist of a two-digit number, a dash,
        and a brief descriptive identifier consisting only of ASCII
        characters.  You don't need to follow this convention, but not doing
        so opens you up to risks w.r.t. encoding and ordering.  The name must
        not contain any whitespace, quotes, or apostrophes.

        A commissioning machine will run each of the scripts in lexicographical
        order.  There are no promises about how non-ASCII characters are
        sorted, or even how upper-case letters are sorted relative to
        lower-case letters.  So where ordering matters, use unique numbers.

        Scripts built into MAAS will have names starting with "00-maas" or
        "99-maas" to ensure that they run first or last, respectively.

        Usually a commissioning script will be just that, a script.  Ideally a
        script should be ASCII text to avoid any confusion over encoding.  But
        in some cases a commissioning script might consist of a binary tool
        provided by a hardware vendor.  Either way, the script gets passed to
        the commissioning machine in the exact form in which it was uploaded.

        :param name: Unique identifying name for the script.  Names should
            follow the pattern of "25-burn-in-hard-disk" (all ASCII, and with
            numbers greater than zero, and generally no "weird" characters).
        :param content: A script file, to be uploaded in binary form.  Note:
            this is not a normal parameter, but a file upload.  Its filename
            is ignored; MAAS will know it by the name you pass to the request.
        """
        content = Bin(get_content_parameter(request))
        data = request.data.copy()
        data["script"] = content
        data["script_type"] = SCRIPT_TYPE.COMMISSIONING
        form = ScriptForm(data=data)
        if form.is_valid():
            script = form.save(request)
            return {
                "name": script.name,
                "content": b64encode(script.script.data.encode()),
                "deprecated": (
                    "The commissioning-scripts endpoint is deprecated. "
                    "Please use the node-scripts endpoint."
                ),
                "resource_uri": reverse(
                    "commissioning_script_handler", args=[script.name]
                ),
            }
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls):
        return ("commissioning_scripts_handler", [])


@deprecated(use=NodeScriptHandler)
class CommissioningScriptHandler(OperationsHandler):
    """
    Manage a custom commissioning script.

    This functionality is only available to administrators.
    """

    api_doc_section_name = "Commissioning script"

    # Relies on Piston's built-in DELETE implementation.  There is no POST.
    create = None

    def read(self, request, name):
        """Read a commissioning script."""
        script = get_object_or_404(Script, name=name)
        return HttpResponse(
            script.script.data, content_type="application/binary"
        )

    def delete(self, request, name):
        """Delete a commissioning script."""
        script = get_object_or_404(Script, name=name)
        script.delete()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            ENDPOINT.API,
            request,
            None,
            description=("Deleted script '%s'." % script.name),
        )
        return rc.DELETED

    def update(self, request, name):
        """Update a commissioning script."""
        script = get_object_or_404(Script, name=name)
        content = Bin(get_content_parameter(request))
        data = request.data.copy()
        data["script"] = content
        data["script_type"] = SCRIPT_TYPE.COMMISSIONING
        form = ScriptForm(instance=script, data=data)
        if form.is_valid():
            form.save(request)
            return rc.ALL_OK
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls, script=None):
        # See the comment in NodeHandler.resource_uri
        script_name = "name"
        if script is not None:
            script_name = script.name
        return ("commissioning_script_handler", (script_name,))
