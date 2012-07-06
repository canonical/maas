'''
@author: shylent
'''
from tftp.backend import FilesystemSynchronousBackend
from tftp.protocol import TFTP
from twisted.internet import reactor
from twisted.python import log
import random
import sys


def main():
    random.seed()
    log.startLogging(sys.stdout)
    reactor.listenUDP(1069, TFTP(FilesystemSynchronousBackend('output')))
    reactor.run()

if __name__ == '__main__':
    main()
