#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from functools import wraps

import structlog

from maasservicelayer.logging.context import Context

logger = structlog.getLogger()


def with_context_activity(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        context = Context()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(context_id=context.context_id)
        logger.info(f"Starting activity {func.__name__}")
        res = await func(*args, **kwargs)
        logger.info(
            "Activity has completed",
            elapsed_time_seconds=context.get_elapsed_time_seconds(),
        )
        return res

    return wrapper


def with_context_workflow(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        context = Context()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(context_id=context.context_id)
        logger.info(f"Starting workflow {func.__qualname__}")
        res = await func(*args, **kwargs)
        logger.info(
            "Workflow has completed",
            elapsed_time_seconds=context.get_elapsed_time_seconds(),
        )
        return res

    return wrapper
