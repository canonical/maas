# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to large file changes."""


from django.db.models.signals import post_delete

from maasserver.models.largefile import (
    delete_large_object_content_later,
    LargeFile,
)
from maasserver.utils.orm import post_commit_do
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def delete_large_object(sender, instance, **kwargs):
    """Delete the large object when the `LargeFile` is deleted.

    This is done using the `post_delete` signal instead of overriding delete
    on `LargeFile`, so it works correctly for both the model and `QuerySet`.
    """
    if instance.content is not None:
        post_commit_do(delete_large_object_content_later, instance.content)


signals.watch(post_delete, delete_large_object, LargeFile)


# Enable all signals by default.
signals.enable()
