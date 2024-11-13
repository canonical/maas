#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import logging
import sys

from pythonjsonlogger import jsonlogger
import structlog
from structlog.contextvars import merge_contextvars

from maasservicelayer.utils.date import utcnow


class CustomJsonFormatter(jsonlogger.JsonFormatter):
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


def configure_logging(level=logging.INFO, query_level=logging.WARNING):
    """
    In order to force third party libraries (uvicorn, sqlalchemy and others) to output JSON logs
    we have to combine structlog and pythonjsonlogger. For more info, see
    https://www.structlog.org/en/stable/standard-library.html#rendering-using-logging-based-formatters.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
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
        wrapper_class=structlog.stdlib.BoundLogger,
        # TODO BEFORE 3.6 RELEASE: in noble we have a newer version of the structlog library and we have this available
        # wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(CustomJsonFormatter())
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Configure sqlalchemy
    logging.getLogger("sqlalchemy.engine").setLevel(query_level)
    logging.getLogger("sqlalchemy.pool").setLevel(query_level)
