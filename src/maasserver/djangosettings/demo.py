# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django DEMO settings for maas project."""

from os.path import abspath

from maasserver.djangosettings import development, import_settings, settings

# We expect the following settings to be overridden. They are mentioned here
# to silence lint warnings.
MIDDLEWARE = None

# Extend base and development settings.
import_settings(settings)
import_settings(development)

MEDIA_ROOT = abspath("media/demo")

# Connect to the DNS server. TODO: Use the signals manager instead.
DNS_CONNECT = True

# Connect to the DHCP server. TODO: Use the signals manager instead.
DHCP_CONNECT = True

# Connect to the PROXY server. TODO: Use the signals manager instead.
PROXY_CONNECT = True

MAAS_CLI = abspath("bin/maas")

# For demo purposes, give nodes unauthenticated access to their metadata
# even if we can't pass boot parameters.  This is not safe; do not
# enable it on a production MAAS.
ALLOW_UNSAFE_METADATA_ACCESS = True
