# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `CommissioningScript`."""

__all__ = [
    'CommissioningScriptHandler',
    'CommissioningScriptsHandler',
    ]

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.api.utils import get_mandatory_param
from metadataserver.fields import Bin
from metadataserver.models import CommissioningScript
from piston3.utils import rc


def get_content_parameter(request):
    """Get the "content" parameter from a CommissioningScript POST or PUT."""
    content_file = get_mandatory_param(request.FILES, 'content')
    return content_file.read()


class CommissioningScriptsHandler(OperationsHandler):
    """Manage custom commissioning scripts.

    This functionality is only available to administrators.
    """
    api_doc_section_name = "Commissioning scripts"

    update = delete = None

    def read(self, request):
        """List commissioning scripts."""
        return [
            script.name
            for script in CommissioningScript.objects.all().order_by('name')]

    def create(self, request):
        """Create a new commissioning script.

        Each commissioning script is identified by a unique name.

        By convention the name should consist of a two-digit number, a dash,
        and a brief descriptive identifier consisting only of ASCII
        characters.  You don't need to follow this convention, but not doing
        so opens you up to risks w.r.t. encoding and ordering.  The name must
        not contain any whitespace, quotes, or apostrophes.

        A commissioning node will run each of the scripts in lexicographical
        order.  There are no promises about how non-ASCII characters are
        sorted, or even how upper-case letters are sorted relative to
        lower-case letters.  So where ordering matters, use unique numbers.

        Scripts built into MAAS will have names starting with "00-maas" or
        "99-maas" to ensure that they run first or last, respectively.

        Usually a commissioning script will be just that, a script.  Ideally a
        script should be ASCII text to avoid any confusion over encoding.  But
        in some cases a commissioning script might consist of a binary tool
        provided by a hardware vendor.  Either way, the script gets passed to
        the commissioning node in the exact form in which it was uploaded.

        :param name: Unique identifying name for the script.  Names should
            follow the pattern of "25-burn-in-hard-disk" (all ASCII, and with
            numbers greater than zero, and generally no "weird" characters).
        :param content: A script file, to be uploaded in binary form.  Note:
            this is not a normal parameter, but a file upload.  Its filename
            is ignored; MAAS will know it by the name you pass to the request.
        """
        name = get_mandatory_param(request.data, 'name')
        content = Bin(get_content_parameter(request))
        return CommissioningScript.objects.create(name=name, content=content)

    @classmethod
    def resource_uri(cls):
        return ('commissioning_scripts_handler', [])


class CommissioningScriptHandler(OperationsHandler):
    """Manage a custom commissioning script.

    This functionality is only available to administrators.
    """
    api_doc_section_name = "Commissioning script"

    model = CommissioningScript
    fields = ('name', 'content')

    # Relies on Piston's built-in DELETE implementation.  There is no POST.
    create = None

    def read(self, request, name):
        """Read a commissioning script."""
        script = get_object_or_404(CommissioningScript, name=name)
        return HttpResponse(script.content, content_type='application/binary')

    def delete(self, request, name):
        """Delete a commissioning script."""
        script = get_object_or_404(CommissioningScript, name=name)
        script.delete()
        return rc.DELETED

    def update(self, request, name):
        """Update a commissioning script."""
        content = Bin(get_content_parameter(request))
        script = get_object_or_404(CommissioningScript, name=name)
        script.content = content
        script.save()

    @classmethod
    def resource_uri(cls, script=None):
        # See the comment in NodeHandler.resource_uri
        script_name = 'name'
        if script is not None:
            script_name = script.name
        return ('commissioning_script_handler', (script_name, ))
