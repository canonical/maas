# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Server application."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'DefaultMeta',
    'logger',
    ]

import logging


logger = logging.getLogger("maasserver")


class DefaultMeta:
    """Base class for model `Meta` classes in the maasserver app.

    Each model in the models package outside of __init__.py needs a nested
    `Meta` class that defines `app_label`.  Otherwise, South won't recognize
    the model and will fail to generate schema migrations for it.
    """
    app_label = 'maasserver'


def execute_from_command_line():
    # On Vivid, we need to explicitly use Django 1.6.
    import os
    import sys
    if os.path.isdir("/usr/lib/django16"):
        sys.path.insert(1, "/usr/lib/django16")

    import django.core.management
    django.core.management.execute_from_command_line()


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
