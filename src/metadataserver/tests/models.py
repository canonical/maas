# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test model for testing BinaryField."""

from django.db.models import Model

from metadataserver.fields import BinaryField


class BinaryFieldModel(Model):
    """Test model for BinaryField.  Contains nothing but a BinaryField."""

    data = BinaryField(null=True)
