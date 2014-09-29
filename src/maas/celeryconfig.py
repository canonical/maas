# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery settings for the region controller."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type


# Each cluster should have its own queue created automatically by Celery.
CELERY_CREATE_MISSING_QUEUES = True

CELERY_IMPORTS = (
    # Tasks.
    "provisioningserver.tasks",
    )

CELERY_ACKS_LATE = True

# Do not store the tasks' return values (aka tombstones);
# This improves performance.
CELERY_IGNORE_RESULT = True

# Don't queue, always run tasks immediately, and propagate exceptions back to
# the caller. This eliminates the need for a queue.
CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
