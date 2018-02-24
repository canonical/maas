# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate ephemeral user-data from template and code snippets.

This combines the snippets of code in the `snippets` directory into
the ephemeral script.

Its contents are not customizable.  To inject custom code, use the
:class:`Script` model.
"""

__all__ = [
    'generate_user_data',
    ]

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os.path

from maasserver.enum import NODE_STATUS
from metadataserver.user_data.snippets import (
    get_snippet_context,
    get_userdata_template_dir,
)
import tempita


ENCODING = 'utf-8'


def generate_user_data(node, userdata_template_file, extra_context=None):
    """Produce a user_data script for use by an ephemeral environment.

    The main template file contains references to so-called ``snippets''
    which are read in here, and substituted.  In addition, the regular
    preseed context variables are available (such as 'http_proxy').

    The final result is a MIME multipart message that consists of a
    'cloud-config' part and an 'x-shellscript' part.  This allows maximum
    flexibility with cloud-init as we read in a template
    'user_data_config.template' to set cloud-init configs before the script
    is run.

    :rtype: `bytes`
    """
    # Avoid circular dependencies.
    from maasserver.preseed import get_preseed_context

    userdata_template = tempita.Template.from_filename(
        userdata_template_file, encoding=ENCODING)
    # The preseed context is a dict containing various configs that the
    # templates can use.
    preseed_context = get_preseed_context(
        rack_controller=node.get_boot_rack_controller())
    preseed_context['node'] = node

    # Render the snippets in the main template.
    snippets = get_snippet_context(encoding=ENCODING)
    snippets.update(preseed_context)
    if extra_context is not None:
        snippets.update(extra_context)
    userdata = userdata_template.substitute(snippets).encode(ENCODING)

    data_part = MIMEText(userdata, 'x-shellscript', ENCODING)
    data_part.add_header(
        'Content-Disposition', 'attachment; filename="user_data.sh"')
    combined = MIMEMultipart()
    combined.attach(data_part)
    return combined.as_bytes()


def generate_user_data_for_status(node, status=None, extra_content=None):
    """Produce a user_data script based on the node's status."""
    templates = {
        NODE_STATUS.COMMISSIONING: 'commissioning.template',
        NODE_STATUS.TESTING: 'script_runner.template',
        NODE_STATUS.DISK_ERASING: 'disk_erasing.template',
        NODE_STATUS.RESCUE_MODE: 'script_runner.template',
    }
    if status is None:
        status = node.status
    userdata_template_file = os.path.join(
        get_userdata_template_dir(), templates[status])
    return generate_user_data(node, userdata_template_file, extra_content)


def generate_user_data_for_poweroff(node):
    """Produce the poweroff user_data script."""
    userdata_template_file = os.path.join(
        get_userdata_template_dir(), 'poweroff.template')
    return generate_user_data(node, userdata_template_file)
