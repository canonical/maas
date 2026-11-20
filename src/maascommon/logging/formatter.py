#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
import logging

from pythonjsonlogger.json import JsonFormatter


class CustomJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record: logging.LogRecord, message_dict):
        super().add_fields(log_record, record, message_dict)

        log_record["logger"] = f"{record.name}:{record.lineno}"
        log_record["level"] = record.levelname
        log_record["thread"] = f"{record.threadName}:{record.thread}"
        if not log_record.get("timestamp"):
            # this doesn't use record.created, so it is slightly off
            log_record["timestamp"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
