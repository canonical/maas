# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate ephemeral user-data from template and code snippets.

This combines the snippets of code in the `snippets` directory into
the ephemeral script.

Its contents are not customizable.  To inject custom code, use the
:class:`Script` model.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os.path

import tempita

from maasserver.enum import NODE_STATUS
from metadataserver.user_data.snippets import (
    get_snippet_context,
    get_userdata_template_dir,
)

ENCODING = "utf-8"


def generate_user_data(
    node,
    userdata_template_file,
    extra_context=None,
    rack_controller=None,
    request=None,
):
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
    # Enlisting machines will not have a node object or an assoicated
    # rack controller if the subnet is unknown to MAAS or MAAS does not
    # control DHCP on the VLAN(see find_rack_controller in maasserver.utils)
    if rack_controller is None and node is not None:
        rack_controller = node.get_boot_rack_controller()

    userdata_template = tempita.Template.from_filename(
        userdata_template_file, encoding=ENCODING
    )

    # Render the snippets in the main template.
    snippets = get_snippet_context(encoding=ENCODING)
    if extra_context is not None:
        snippets.update(extra_context)
    userdata = userdata_template.substitute(snippets).encode(ENCODING)

    data_part = MIMEText(userdata, "x-shellscript", ENCODING)
    data_part.add_header(
        "Content-Disposition", 'attachment; filename="user_data.sh"'
    )
    combined = MIMEMultipart()
    combined.attach(data_part)
    return combined.as_bytes()


def generate_user_data_for_status(
    node, status=None, extra_content=None, rack_controller=None, request=None
):
    """Produce a user_data script based on the node's status."""
    if status is None:
        status = node.status

    if status == NODE_STATUS.DISK_ERASING:
        template = "disk_erasing.template"
    else:
        template = "script_runner.template"

    userdata_template_file = os.path.join(
        get_userdata_template_dir(), template
    )
    return generate_user_data(
        node, userdata_template_file, extra_content, rack_controller, request
    )


def generate_user_data_for_poweroff(node, request=None):
    """Produce the poweroff user_data script."""
    userdata_template_file = os.path.join(
        get_userdata_template_dir(), "poweroff.template"
    )
    return generate_user_data(node, userdata_template_file, request=request)
