# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# TODO: Module docstring.
"""..."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
# TODO: Your class name here.
    'ModelClass',
    ]


from django.db.models import (
    Manager,
    Model,
    )
# TODO: s/maasserver/metadataserver/ when using in metadataserver.
from maasserver import DefaultMeta


class ModelManager(Manager):
    """Manager for model class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """


# TODO: Your class name here.
class ModelClass(Model):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = ModelManager()
