# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test related classes and functions for maas and its applications."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'JSONFieldModel',
    ]

from django.db import models
from maasserver.fields import JSONObjectField
from maasserver.models import CommonInfo


class JSONFieldModel(models.Model):
    name = models.CharField(max_length=255, unique=False)
    value = JSONObjectField(null=True)


class MessagesTestModel(models.Model):
    name = models.CharField(max_length=255, unique=False)


class CommonInfoTestModel(CommonInfo):
    # This model inherits from CommonInfo so it will have a 'created'
    # field and an 'updated' field.
    pass
