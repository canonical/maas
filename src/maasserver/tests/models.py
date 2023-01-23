# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test related classes and functions for maas and its applications."""

__all__ = [
    "BulkManagerParentTestModel",
    "BulkManagerTestModel",
    "CIDRTestModel",
    "FieldChangeTestModel",
    "GenericTestModel",
    "IPv4CIDRTestModel",
    "LargeObjectFieldModel",
    "MessagesTestModel",
    "TimestampedModelTestModel",
    "XMLFieldModel",
]

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Model,
    OneToOneField,
)

from maasserver.fields import (
    CIDRField,
    IPv4CIDRField,
    LargeObjectField,
    XMLField,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.managers import BulkManager
from maasserver.models.timestampedmodel import TimestampedModel


class GenericTestModel(Model):
    """A multi-purpose test model with one field, named `field`."""

    field = CharField(max_length=20, blank=True)


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


class TimestampedOneToOneTestModel(TimestampedModel):
    # This model inherits from TimestampedModel so it will have a 'created'
    # field and an 'updated' field.
    generic = OneToOneField(
        GenericTestModel,
        null=False,
        blank=False,
        on_delete=CASCADE,
        primary_key=True,
    )


class FieldChangeTestModel(Model):
    name1 = CharField(max_length=255, unique=False)
    name2 = CharField(max_length=255, unique=False)


class BulkManagerParentTestModel(Model):
    pass


class BulkManagerTestModel(Model):
    parent = ForeignKey(
        "BulkManagerParentTestModel", editable=False, on_delete=CASCADE
    )

    objects = BulkManager()


class LargeObjectFieldModel(Model):
    name = CharField(max_length=255, unique=False)
    large_object = LargeObjectField(block_size=10)


class CIDRTestModel(Model):
    cidr = CIDRField()


class IPv4CIDRTestModel(Model):
    cidr = IPv4CIDRField()


class CleanSaveTestModel(CleanSave, Model):
    field = CharField(max_length=20, null=True, blank=True)
    related = ForeignKey(
        GenericTestModel, null=True, blank=True, on_delete=CASCADE
    )

    def __test_prop_get(self):
        return self.__inner

    def __test_prop_set(self, value):
        self.__inner = value

    test_prop = property(__test_prop_get, __test_prop_set)
