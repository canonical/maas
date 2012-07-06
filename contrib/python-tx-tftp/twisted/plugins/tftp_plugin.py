'''
@author: shylent
'''
from tftp.backend import FilesystemSynchronousBackend
from tftp.protocol import TFTP
from twisted.application import internet
from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.filepath import FilePath
from zope.interface import implements


def to_path(str_path):
    return FilePath(str_path)

class TFTPOptions(usage.Options):
    optFlags = [
        ['enable-reading', 'r', 'Lets the clients read from this server.'],
        ['enable-writing', 'w', 'Lets the clients write to this server.'],
        ['verbose', 'v', 'Make this server noisy.']
    ]
    optParameters = [
        ['port', 'p', 1069, 'Port number to listen on.', int],
        ['root-directory', 'd', None, 'Root directory for this server.', to_path]
    ]

    def postOptions(self):
        if self['root-directory'] is None:
            raise usage.UsageError("You must provide a root directory for the server")


class TFTPServiceCreator(object):
    implements(IServiceMaker, IPlugin)
    tapname = "tftp"
    description = "A TFTP Server"
    options = TFTPOptions

    def makeService(self, options):
        backend = FilesystemSynchronousBackend(options["root-directory"],
                                               can_read=options['enable-reading'],
                                               can_write=options['enable-writing'])
        return internet.UDPServer(options['port'], TFTP(backend))

serviceMaker = TFTPServiceCreator()
