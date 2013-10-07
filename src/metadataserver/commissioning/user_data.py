# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate commissioning user-data from template and code snippets.

This combines the `user_data.template` and the snippets of code in the
`snippets` directory into the main commissioning script.

Its contents are not customizable.  To inject custom code, use the
:class:`CommissioningScript` model.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'generate_user_data',
    ]

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os.path

from maasserver.preseed import get_preseed_context
from metadataserver.commissioning.snippets import (
    get_snippet_context,
    get_userdata_template_dir,
    )
import tempita


ENCODING = 'utf-8'


def generate_user_data(nodegroup=None):
    """Produce the main commissioning script.

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
    commissioning_dir = get_userdata_template_dir()
    userdata_template_file = os.path.join(
        commissioning_dir, 'user_data.template')
    config_template_file = os.path.join(
        commissioning_dir, 'user_data_config.template')
    userdata_template = tempita.Template.from_filename(
        userdata_template_file, encoding=ENCODING)
    config_template = tempita.Template.from_filename(
        config_template_file, encoding=ENCODING)
    # The preseed context is a dict containing various configs that the
    # templates can use.
    preseed_context = get_preseed_context(nodegroup=nodegroup)

    # Render the snippets in the main template.
    snippets = get_snippet_context(encoding=ENCODING)
    snippets.update(preseed_context)
    userdata = userdata_template.substitute(snippets).encode(ENCODING)

    # Render the config.
    config = config_template.substitute(preseed_context)

    # Create a MIME multipart message from the config and the userdata.
    config_part = MIMEText(config, 'cloud-config', ENCODING)
    config_part.add_header(
        'Content-Disposition', 'attachment; filename="config"')
    data_part = MIMEText(userdata, 'x-shellscript', ENCODING)
    data_part.add_header(
        'Content-Disposition', 'attachment; filename="user_data.sh"')
    combined = MIMEMultipart()
    combined.attach(config_part)
    combined.attach(data_part)
    return combined.as_string()
