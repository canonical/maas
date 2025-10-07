# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import contextvars
import uuid

TRACE_ID = contextvars.ContextVar("_MAAS_TRACE_ID", default="")


def get_trace_id() -> str:
    return TRACE_ID.get()


def set_trace_id(trace_id: str) -> None:
    TRACE_ID.set(trace_id)


def get_or_set_trace_id() -> str:
    trace_id = TRACE_ID.get()
    if not trace_id:
        # If this is a new context, generate a new trace id.
        trace_id = uuid.uuid4().hex
        TRACE_ID.set(trace_id)
    return trace_id
