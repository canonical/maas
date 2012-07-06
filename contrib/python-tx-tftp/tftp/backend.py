'''
@author: shylent
'''
from os import fstat
from tftp.errors import Unsupported, FileExists, AccessViolation, FileNotFound
from twisted.python.filepath import FilePath, InsecurePath
import shutil
import tempfile
from zope import interface

class IBackend(interface.Interface):
    """An object, that manages interaction between the TFTP network protocol and
    anything, where you can get files from or put files to (a filesystem).

    """

    def get_reader(file_name):
        """Return an object, that provides L{IReader}, that was initialized with
        the given L{file_name}.

        @param file_name: file name, specified as part of a TFTP read request (RRQ)
        @type file_name: C{str}

        @raise Unsupported: if reading is not supported for this particular
        backend instance

        @raise AccessViolation: if the passed file_name is not acceptable for
        security or access control reasons

        @raise FileNotFound: if the file, that corresponds to the given C{file_name}
        could not be found

        @raise BackendError: for any other errors, that were encountered while
        attempting to construct a reader

        @return: an object, that provides L{IReader}, or a L{Deferred} that
        will fire with an L{IReader}

        """

    def get_writer(file_name):
        """Return an object, that provides L{IWriter}, that was initialized with
        the given L{file_name}.

        @param file_name: file name, specified as part of a TFTP write request (WRQ)
        @type file_name: C{str}

        @raise Unsupported: if writing is not supported for this particular
        backend instance

        @raise AccessViolation: if the passed file_name is not acceptable for
        security or access control reasons

        @raise FileExists: if the file, that corresponds to the given C{file_name}
        already exists and it is not desirable to overwrite it

        @raise BackendError: for any other errors, that were encountered while
        attempting to construct a writer

        @return: an object, that provides L{IWriter}, or a L{Deferred} that
        will fire with an L{IWriter}

        """

class IReader(interface.Interface):
    """An object, that performs reads on request of the TFTP protocol"""

    size = interface.Attribute(
        "The size of the file to be read, or C{None} if it's not known.")

    def read(size):
        """Attempt to read C{size} number of bytes.

        @note: If less, than C{size} bytes is returned, it is assumed, that there
        is no more data to read and the TFTP transfer is terminated. This means, that
        less, than C{size} bytes should be returned if and only if this read should
        be the last read for this reader object.

        @param size: a number of bytes to return to the protocol
        @type size: C{int}

        @return: data, that was read or a L{Deferred}, that will be fired with
        the data, that was read.
        @rtype: C{str} or L{Deferred}

        """

    def finish():
        """Release the resources, that were acquired by this reader and make sure,
        that no additional data will be returned.

        """


class IWriter(interface.Interface):
    """An object, that performs writes on request of the TFTP protocol"""

    def write(data):
        """Attempt to write the data

        @return: C{None} or a L{Deferred}, that will fire with C{None} (any errors,
        that occured during the write will be available in an errback)
        @rtype: C{NoneType} or L{Deferred}

        """

    def finish():
        """Tell this writer, that there will be no more data and that the transfer
        was successfully completed

        """

    def cancel():
        """Tell this writer, that the transfer has ended unsuccessfully"""


class FilesystemReader(object):
    """A reader to go with L{FilesystemSynchronousBackend}.

    @see: L{IReader}

    @param file_path: a path to file, that we will read from
    @type file_path: L{FilePath<twisted.python.filepath.FilePath>}

    @raise FileNotFound: if the file does not exist

    """

    interface.implements(IReader)

    def __init__(self, file_path):
        self.file_path = file_path
        try:
            self.file_obj = self.file_path.open('r')
        except IOError:
            raise FileNotFound(self.file_path)
        self.state = 'active'

    @property
    def size(self):
        """
        @see: L{IReader.size}

        """
        if self.file_obj.closed:
            return None
        else:
            return fstat(self.file_obj.fileno()).st_size

    def read(self, size):
        """
        @see: L{IReader.read}

        @return: data, that was read
        @rtype: C{str}

        """
        if self.state in ('eof', 'finished'):
            return ''
        data = self.file_obj.read(size)
        if not data:
            self.state = 'eof'
            self.file_obj.close()
        return data

    def finish(self):
        """
        @see: L{IReader.finish}

        """
        if self.state not in ('eof', 'finished'):
            self.file_obj.close()
        self.state = 'finished'


class FilesystemWriter(object):
    """A writer to go with L{FilesystemSynchronousBackend}.

    This particular implementation actually writes to a temporary file. If the
    transfer is completed successfully, contens of the target file are replaced
    with the contents of the temporary file and the temporary file is removed.
    If L{cancel} is called, both files are discarded.

    @see: L{IWriter}

    @param file_path: a path to file, that will be created and written to
    @type file_path: L{FilePath<twisted.python.filepath.FilePath>}

    @raise FileExists: if the file already exists

    """

    interface.implements(IWriter)

    def __init__(self, file_path):
        if file_path.exists():
            raise FileExists(file_path)
        self.file_path = file_path
        self.destination_file = self.file_path.open('w')
        self.temp_destination = tempfile.TemporaryFile()
        self.state = 'active'

    def write(self, data):
        """
        @see: L{IWriter.write}

        """
        self.temp_destination.write(data)

    def finish(self):
        """
        @see: L{IWriter.finish}

        """
        if self.state not in ('finished', 'cancelled'):
            self.temp_destination.seek(0)
            shutil.copyfileobj(self.temp_destination, self.destination_file)
            self.temp_destination.close()
            self.destination_file.close()
            self.state = 'finished'

    def cancel(self):
        """
        @see: L{IWriter.cancel}

        """
        if self.state not in ('finished', 'cancelled'):
            self.temp_destination.close()
            self.destination_file.close()
            self.file_path.remove()
            self.state = 'cancelled'


class FilesystemSynchronousBackend(object):
    """A synchronous filesystem backend.

    @see: L{IBackend}

    @param base_path: the base filesystem path for this backend, any attempts to
    read or write 'above' the specified path will be denied
    @type base_path: C{str} or L{FilePath<twisted.python.filepath.FilePath>}

    @param can_read: whether or not this backend should support reads
    @type can_read: C{bool}

    @param can_write: whether or not this backend should support writes
    @type can_write: C{bool}

    """

    interface.implements(IBackend)

    def __init__(self, base_path, can_read=True, can_write=True):
        try:
            self.base = FilePath(base_path.path)
        except AttributeError:
            self.base = FilePath(base_path)
        self.can_read, self.can_write = can_read, can_write

    def get_reader(self, file_name):
        """
        @see: L{IBackend.get_reader}

        @return: an object, providing L{IReader}
        @rtype: L{FilesystemReader}

        """
        if not self.can_read:
            raise Unsupported("Reading not supported")
        try:
            target_path = self.base.child(file_name)
        except InsecurePath, e:
            raise AccessViolation("Insecure path: %s" % e)
        return FilesystemReader(target_path)

    def get_writer(self, file_name):
        """
        @see: L{IBackend.get_writer}

        @return: an object, providing L{IWriter}
        @rtype: L{FilesystemWriter}

        """
        if not self.can_write:
            raise Unsupported("Writing not supported")
        try:
            target_path = self.base.child(file_name)
        except InsecurePath, e:
            raise AccessViolation("Insecure path: %s" % e)
        return FilesystemWriter(target_path)
