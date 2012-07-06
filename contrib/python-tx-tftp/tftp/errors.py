'''
@author: shylent
'''

class TFTPError(Exception):
    """Base exception class for this package"""

class WireProtocolError(TFTPError):
    """Base exception class for wire-protocol level errors"""

class InvalidOpcodeError(WireProtocolError):
    """An invalid opcode was encountered"""

    def __init__(self, opcode):

        super(InvalidOpcodeError, self).__init__("Invalid opcode: %s" % opcode)

class PayloadDecodeError(WireProtocolError):
    """Failed to parse the payload"""

class OptionsDecodeError(PayloadDecodeError):
    """Failed to parse options in the WRQ/RRQ datagram. It is distinct from
    L{PayloadDecodeError} so that it can be caught and dealt with gracefully
    (pretend we didn't see any options at all, perhaps).

    """

class InvalidErrorcodeError(PayloadDecodeError):
    """An ERROR datagram has an error code, that does not correspond to any known
    error code values.

    @ivar errorcode: The error code, that we were unable to parse
    @type errorcode: C{int}
    
    """

    def __init__(self, errorcode):
        self.errorcode = errorcode
        super(InvalidErrorcodeError, self).__init__("Unknown error code: %s" % errorcode)

class BackendError(TFTPError):
    """Base exception class for backend errors"""

class Unsupported(BackendError):
    """Requested operation (read/write) is not supported"""

class AccessViolation(BackendError):
    """Illegal filesystem operation. Corresponds to the "(2) Access violation"
    TFTP error code.

    One of the prime examples of these is an attempt at directory traversal.

    """

class FileNotFound(BackendError):
    """File not found.

    Corresponds to the "(1) File not found" TFTP error code.

    @ivar file_path: Path to the file, that was requested
    @type file_path: C{str} or L{twisted.python.filepath.FilePath}

    """

    def __init__(self, file_path):
        self.file_path = file_path

    def __str__(self):
        return "File not found: %s" % self.file_path


class FileExists(BackendError):
    """File exists.

    Corresponds to the "(6) File already exists" TFTP error code.

    @ivar file_path: Path to file
    @type file_path: C{str} or L{twisted.python.filepath.FilePath}
    
    """

    def __init__(self, file_path):
        self.file_path = file_path

    def __str__(self):
        return "File already exists: %s" % self.file_path
