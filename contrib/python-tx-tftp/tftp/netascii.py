'''
@author: shylent
'''
# So basically, the idea is that in netascii a *newline* (whatever that is 
# on the current platform) is represented by a CR+LF sequence and a single CR
# is represented by CR+NUL.

from twisted.internet.defer import maybeDeferred, succeed
import os
import re

__all__ = ['NetasciiSenderProxy', 'NetasciiReceiverProxy',
           'to_netascii', 'from_netascii']

CR = '\x0d'
LF = '\x0a'
CRLF = CR + LF
NUL = '\x00'
CRNUL = CR + NUL

NL = os.linesep


re_from_netascii = re.compile('(\x0d\x0a|\x0d\x00)')

def _convert_from_netascii(match_obj):
    if match_obj.group(0) == CRLF:
        return NL
    elif match_obj.group(0) == CRNUL:
        return CR

def from_netascii(data):
    """Convert a netascii-encoded string into a string with platform-specific
    newlines.

    """
    return re_from_netascii.sub(_convert_from_netascii, data)

# So that I can easily switch the NL around in tests
_re_to_netascii = '(%s|\x0d)'
re_to_netascii = re.compile(_re_to_netascii % NL)

def _convert_to_netascii(match_obj):
    if match_obj.group(0) == NL:
        return CRLF
    elif match_obj.group(0) == CR:
        return CRNUL

def to_netascii(data):
    """Convert a string with platform-specific newlines into netascii."""
    return re_to_netascii.sub(_convert_to_netascii, data)

class NetasciiReceiverProxy(object):
    """Proxies an object, that provides L{IWriter}. Incoming data is transformed
    as follows:
        - CR+LF is replaced with the platform-specific newline
        - CR+NUL is replaced with CR

    @param writer: an L{IWriter} object, that will be used to perform the actual writes
    @type writer: L{IWriter} provider

    """

    def __init__(self, writer):
        self.writer = writer
        self._carry_cr = False

    def write(self, data):
        """Attempt a write, performing transformation as described in
        L{NetasciiReceiverProxy}. May write 1 byte less, than provided, if the last
        byte in the chunk is a CR.

        @param data: data to be written
        @type data: C{str}

        @return: L{Deferred}, that will be fired when the write is complete
        @rtype: L{Deferred}

        """
        if self._carry_cr:
            data = CR + data
        data = from_netascii(data)
        if data.endswith(CR):
            self._carry_cr = True
            return maybeDeferred(self.writer.write, data[:-1])
        else:
            self._carry_cr = False
            return maybeDeferred(self.writer.write, data)

    def __getattr__(self, name):
        return getattr(self.writer, name)


class NetasciiSenderProxy(object):
    """Proxies an object, that provides L{IReader}. The data that is read is
    transformed as follows:
        - platform-specific newlines are replaced with CR+LF
        - freestanding CR are replaced with CR+NUL

    @param reader: an L{IReader} object
    @type reader: L{IReader} provider

    """

    def __init__(self, reader):
        self.reader = reader
        self.buffer = ''

    def read(self, size):
        """Attempt to read C{size} bytes, transforming them as described in
        L{NetasciiSenderProxy}.

        @param size: number of bytes to read
        @type size: C{int}

        @return: L{Deferred}, that will be fired with exactly C{size} bytes,
        regardless of the transformation, that was performed if there is more data,
        or less, than C{size} bytes if there is no more data to read.
        @rtype: L{Deferred}

        """
        need_bytes = size - len(self.buffer)
        if need_bytes <= 0:
            data, self.buffer = self.buffer[:size], self.buffer[size:]
            return succeed(data)
        d = maybeDeferred(self.reader.read, need_bytes)
        d.addCallback(self._gotDataFromReader, size)
        return d

    def _gotDataFromReader(self, data, size):
        data = self.buffer + to_netascii(data)
        data, self.buffer = data[:size], data[size:]
        return data

    def __getattr__(self, name):
        return getattr(self.reader, name)
