#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Print information from the Cobbler server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type

import sys
import xmlrpclib


host = "192.168.123.2"
user = "cobbler"
password = "xcobbler"
if len(sys.argv) >= 2:
    host = sys.argv[1]
if len(sys.argv) >= 3:
    user = sys.argv[2]
if len(sys.argv) >= 4:
    password = sys.argv[3]

if not host.startswith('http://'):
    host = "http://%s/cobbler_api" % host

server = xmlrpclib.Server(host)
token = server.login(user, password)

distros = server.get_distros()
print("::::::::::: distros :::::::::::")
for d in server.get_distros():
    print("%s: breed=%s, os_version=%s, mgmt_classes=%s" %
         (d['name'], d['breed'], d['os_version'], d['mgmt_classes']))

profiles = server.get_profiles() 
print("\n::::::::::: profiles :::::::::::")
for d in server.get_profiles():
    print("%s: distro=%s parent=%s kickstart=%s" %
         (d['name'], d['distro'], d['parent'], d['kickstart']))

print("\n::::::::::: servers :::::::::::")
for s in server.get_systems():
    print(s['interfaces'])
