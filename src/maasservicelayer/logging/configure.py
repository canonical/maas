#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import logging
import sys

from pythonjsonlogger.json import JsonFormatter
import structlog
from structlog.contextvars import merge_contextvars

from maasservicelayer.utils.date import utcnow


class CustomJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record: logging.LogRecord, message_dict):
        super(CustomJsonFormatter, self).add_fields(
            log_record, record, message_dict
        )

        log_record["logger"] = f"{record.name}:{record.lineno}"
        log_record["level"] = record.levelname
        log_record["thread"] = f"{record.threadName}:{record.thread}"
        if not log_record.get("timestamp"):
            # this doesn't use record.created, so it is slightly off
            log_record["timestamp"] = utcnow().strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )


_json_handler: logging.Handler | None = None


def configure_logging(level=logging.INFO, query_level=logging.WARNING):
    """
    In order to force third party libraries (uvicorn, sqlalchemy and others) to output JSON logs
    we have to combine structlog and pythonjsonlogger. For more info, see
    https://www.structlog.org/en/stable/standard-library.html#rendering-using-logging-based-formatters.
    """
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Transform event dict into `logging.Logger` method arguments.
            # "event" becomes "msg" and the rest is passed as a dict in
            # "extra". IMPORTANT: This means that the standard library MUST
            # render "extra" for the context to appear in log entries! See
            # warning below.
            structlog.stdlib.render_to_log_kwargs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    global _json_handler
    if _json_handler is None:
        # Bind the handler to the process' real stdout: under pytest
        # sys.stdout is a per-test capture that is closed when the test
        # ends, which turns any later record (e.g. from the session-long
        # crochet reactor) into "I/O operation on closed file" errors.
        # Create it only once, so repeated calls don't stack duplicate
        # handlers on the root logger.
        _json_handler = logging.StreamHandler(stream=sys.__stdout__)
        _json_handler.setFormatter(CustomJsonFormatter())
        logging.getLogger().addHandler(_json_handler)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Configure sqlalchemy
    logging.getLogger("sqlalchemy.engine").setLevel(query_level)
    logging.getLogger("sqlalchemy.pool").setLevel(query_level)

    # httpx talks too much
    logging.getLogger("httpx").setLevel(logging.WARNING)
