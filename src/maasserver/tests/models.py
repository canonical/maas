# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test related classes and functions for maas and its applications."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BulkManagerParentTestModel',
    'BulkManagerTestModel',
    'FieldChangeTestModel',
    'GenericTestModel',
    'JSONFieldModel',
    'LargeObjectFieldModel',
    'MAASIPAddressFieldModel',
    'MessagesTestModel',
    'TimestampedModelTestModel',
    'XMLFieldModel',
    ]

from django.db.models import (
    CharField,
    ForeignKey,
    Model,
)
from maasserver.fields import (
    JSONObjectField,
    LargeObjectField,
    MAASIPAddressField,
    XMLField,
)
from maasserver.models.managers import BulkManager
from maasserver.models.timestampedmodel import TimestampedModel


class GenericTestModel(Model):
    """A multi-purpose test model with one field, named `field`."""
    field = CharField(max_length=20, blank=True)


class JSONFieldModel(Model):
    name = CharField(max_length=255, unique=False)
    value = JSONObjectField(null=True)


class XMLFieldModel(Model):

    class Meta:
        db_table = "docs"

    name = CharField(max_length=255, unique=False)
    value = XMLField(null=True)


class MessagesTestModel(Model):
    name = CharField(max_length=255, unique=False)


class TimestampedModelTestModel(TimestampedModel):
    # This model inherits from TimestampedModel so it will have a 'created'
    # field and an 'updated' field.
    pass


class FieldChangeTestModel(Model):
    name1 = CharField(max_length=255, unique=False)
    name2 = CharField(max_length=255, unique=False)


class BulkManagerParentTestModel(Model):
    pass


class BulkManagerTestModel(Model):
    parent = ForeignKey('BulkManagerParentTestModel', editable=False)

    objects = BulkManager()


class MAASIPAddressFieldModel(Model):
    ip_address = MAASIPAddressField()


class LargeObjectFieldModel(Model):
    name = CharField(max_length=255, unique=False)
    large_object = LargeObjectField(block_size=10)
