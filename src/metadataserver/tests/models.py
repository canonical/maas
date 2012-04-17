# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test model for testing BinaryField."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "BinaryFieldModel",
    ]

from django.db.models import Model
from metadataserver.fields import BinaryField


class BinaryFieldModel(Model):
    """Test model for BinaryField.  Contains nothing but a BinaryField."""

    data = BinaryField(null=True)
