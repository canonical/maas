# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery logging."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'task_logger',
    ]


from celery.log import get_task_logger

# Celery task logger.  Shared between tasks, as per Celery's recommended
# practice.
task_logger = get_task_logger()
