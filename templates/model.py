# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# TODO: Module docstring.
"""..."""

__all__ = [
    # TODO: Your class name here.
    'ModelClass',
    ]


from django.db.models import (
    Manager,
    Model,
)
# TODO: Import the DefaultMeta from the appropriate app, e.g. metadataserver.
from maasserver import DefaultMeta


class ModelManager(Manager):
    """Manager for model class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

# TODO: Import your model into, and export it from, models/__init__.py


# TODO: Your class name here.
class ModelClass(Model):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = ModelManager()
