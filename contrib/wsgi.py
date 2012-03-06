# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""WSGI Application."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
import sys

import django.core.handlers.wsgi


current_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'maas.settings'
application = django.core.handlers.wsgi.WSGIHandler()
