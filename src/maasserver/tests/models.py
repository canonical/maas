# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test related classes and functions for maas and its applications."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'JSONFieldModel',
    ]

from django.db import models
from maasserver.fields import JSONObjectField


class JSONFieldModel(models.Model):
    name = models.CharField(max_length=255, unique=False)
    value = JSONObjectField(null=True)
