# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django PERFORMANCE TESTING settings for maas project."""
from maasserver.djangosettings import development, import_settings

import_settings(development)

DEBUG = False
DEBUG_QUERIES = False
DEBUG_QUERIES_LOG_ALL = False
