# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Logging for MAAS, redirects to syslog."""

from collections import deque
import logging
import logging.handlers
import socket


class MAASLogger(logging.getLoggerClass()):
    """A Logger class that doesn't allow you to call exception()."""

    def exception(self, *args, **kwargs):
        raise NotImplementedError(
            "Don't log exceptions to maaslog; use the default "
            "Django logger instead"
        )


class MAASSysLogHandler(logging.handlers.SysLogHandler):
    """A syslog handler that queuess messages when connection to the socket
    cannot be performed.

    Once the connection is made the queue is flushed to the socket.
    """

    def __init__(self, *args, **kwargs):
        # `queue` must be set before `super().__init__`, because
        # `_connect_unixsocket` is called inside.
        self.queue = deque()
        super().__init__(*args, **kwargs)

    def _connect_unixsocket(self, address):
        super()._connect_unixsocket(address)
        # Successfully connected to the socket. Write any queued messages.
        while len(self.queue) > 0:
            msg = self.queue.popleft()
            try:
                self.socket.send(msg)
            except OSError:
                self.queue.appendleft(msg)
                raise

    def emit(self, record):
        """
        Emit a record.

        The record is formatted, and then sent to the syslog server. If
        exception information is present, it is NOT sent to the server.

        Note: This is copied directly from the python3 source code, only the
        modification of appending to the queue was added.
        """
        try:
            msg = self.format(record)
            if self.ident:
                msg = self.ident + msg
            if self.append_nul:
                msg += "\000"

            # We need to convert record level to lowercase, maybe this will
            # change in the future.
            prio = "<%d>" % self.encodePriority(
                self.facility, self.mapPriority(record.levelname)
            )
            prio = prio.encode("utf-8")
            # Message is a string. Convert to bytes as required by RFC 5424
            msg = msg.encode("utf-8")
            msg = prio + msg

            if not self.socket:
                self.createSocket()

            if self.unixsocket:
                try:
                    self.socket.send(msg)
                except OSError:
                    self.socket.close()
                    try:
                        self._connect_unixsocket(self.address)
                    except OSError:
                        # Queue the message to send when the connection
                        # is finally made to the socket.
                        self.queue.append(msg)
                        return
                    self.socket.send(msg)
            elif self.socktype == socket.SOCK_DGRAM:
                self.socket.sendto(msg, self.address)
            else:
                self.socket.sendall(msg)
        except Exception:
            self.handleError(record)


def get_maas_logger(syslog_tag=None):
    """Return a MAAS logger that will log to syslog.

    :param syslog_tag: A string that will be used to prefix the message
        in syslog. Will be appended to "maas" in the form
        "maas.<syslog_tag>". If None, the syslog tag will simply be
        "maas". syslog_tag is also used to name the logger with the
        Python logging module; loggers will be named "maas.<syslog_tag>"
        unless syslog_tag is None.
    """
    if syslog_tag is None:
        logger_name = "maas"
    else:
        logger_name = "maas.%s" % syslog_tag

    maaslog = logging.getLogger(logger_name)
    # This line is pure filth, but it allows us to return MAASLoggers
    # for any logger constructed by this function, whilst leaving all
    # other loggers to be the domain of the logging package.
    maaslog.__class__ = MAASLogger

    return maaslog
