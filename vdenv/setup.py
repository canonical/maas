#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Setup a Virtual Data-center Environment."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type

import os
import re
import subprocess
import sys
import xmlrpclib

from Cheetah.Template import Template
import libvirt
import yaml


NODES_RANGE = range(1,4)

def yaml_loadf(fname):
    fp = open(fname)
    ret = yaml.load(fp)
    fp.close()
    return(ret)

class Domain:
    def __init__(self, syscfg, ident, basedir=None):
        self.ip_pre = syscfg['network']['ip_pre']
        if basedir == None:
            basedir = os.path.abspath(os.curdir)
        self.basedir = basedir
        self._setcfg(syscfg,ident)
        self.network = syscfg['network']['name']

    def __repr__(self):
        return("== %s ==\n ip: %s\n mac: %s\n template: %s\n" %
               (self.name, self.ipaddr, self.mac, self.template))

    @property
    def ipaddr(self):
        return("%s.%s" % (self.ip_pre, self.ipnum))

    @property
    def disk0(self):
        return("%s/%s-disk0.img" % (self.basedir, self.name))

    def dictInfo(self):
        ret = vars(self)
        # have to add the getters
        for prop in ( "ipaddr", "disk0" ):
            ret[prop] = getattr(self,prop)
        return ret

    def toLibVirtXml(self):
        template = Template(file=self.template, searchList=[self.dictInfo()])
        return template.respond()

class Node(Domain):
    def _setcfg(self, cfg, num):
        cfg = cfg['nodes']
        self.name = "%s%02i" % (cfg['prefix'],num)
        self.mac = "%s:%02x" % (cfg['mac_pre'],num)
        self.ipnum = num + 100
        self.template = cfg['template']
        self.mem = cfg['mem'] * 1024
        return

class System(Domain):
    def _setcfg(self, cfg, ident):
        cfg = cfg['systems'][ident]
        self.name = ident
        self.mac = cfg['mac']
        self.ipnum = cfg['ip']
        self.template = cfg['template']
        self.mem = cfg['mem'] * 1024

def renderSysDom(config, syscfg, stype="node"):
    template = Template(file=syscfg['template'], searchList=[config, syscfg])
    return template.respond()

# cobbler:
#  ip: 2 # ip address must be in dhcp range
#  mac: 00:16:3e:3e:a9:1a
#  template: libvirt-system.tmpl
#  mem: 524288
#    
#nodes:
# prefix: node
# mac_pre: 00:16:3e:3e:aa
# mam: 256

def writeDomXmlFile(dom, outpre=""):
    fname="%s%s.xml" % (outpre, dom.name)
    output = open(fname,"w")
    output.write(dom.toLibVirtXml())
    output.close()
    return fname

def libvirt_setup(config):
    conn = libvirt.open("qemu:///system")
    netname = config['network']['name']
    if netname in conn.listDefinedNetworks() or netname in conn.listNetworks():
        net = conn.networkLookupByName(netname)
        if net.isActive():
            net.destroy()
        net.undefine()

    allsys = {}
    for system in config['systems']:
        d = System(config, system)
        allsys[d.name]=d.dictInfo()
    for num in NODES_RANGE:
        d = Node(config, num)
        allsys[d.name]=d.dictInfo()

    conn.networkDefineXML(Template(file=config['network']['template'],
                          searchList=[config['network'],
                                      {'all_systems': allsys }]).respond())

    print("defined network %s " % netname)

    cob = System(config, "zimmer")
    systems = [ cob ]

    for node in NODES_RANGE:
        systems.append(Node(config, node))

    qcow_create = "qemu-img create -f qcow2 %s 2G"
    defined_systems = conn.listDefinedDomains()
    for system in systems:
        if system.name in defined_systems:
            dom = conn.lookupByName(system.name)
            if dom.isActive():
                dom.destroy()
            dom.undefine()
        conn.defineXML(system.toLibVirtXml())
        if isinstance(system,Node):
            subprocess.check_call(qcow_create % system.disk0, shell=True)
        print("defined domain %s" % system.name)

def cobbler_addsystem(server, token, system, profile, hostip):
    eth0 = {
        "macaddress-eth0" : system.mac,
        "ipaddress-eth0" : system.ipaddr,
        "static-eth0" : False,
    }
    items = {
        'name': system.name,
        'hostname': system.name,
        'power_address': "qemu+tcp://%s:65001" % hostip,
        'power_id': system.name,
        'power_type': "virsh",
        'profile': profile,
        'netboot_enabled': True,
        'modify_interface': eth0,
    }

    if len(server.find_system({"name": system.name})):
        server.remove_system(system.name,token)
        server.update()
        print("removed existing %s" % system.name)

    sid = server.new_system(token)
    for key, val in items.iteritems():
        ret = server.modify_system(sid, key, val, token)
        if not ret:
            raise Exception("failed for %s [%s]: %s, %s" %
                            (system.name, ret, key, val))
    ret = server.save_system(sid,token)
    if not ret:
        raise Exception("failed to save %s" % system.name)
    print("added %s" % system.name)


def get_profile_arch():
    """Get the system architecture for use in the cobbler setup profile."""
    # This should, for any given system, match what the zimmer-build
    # script does to determine the right architecture.
    arch_text = subprocess.check_output(['/bin/uname', '-m']).strip()
    if re.match('i.86', arch_text):
        return 'i386'
    else:
        return arch_text


def cobbler_setup(config):
    hostip = "%s.1" % config['network']['ip_pre']
    arch = get_profile_arch()
    profile = "maas-precise-%s" % arch
    
    cob = System(config, "zimmer")
    cobbler_url = "http://%s/cobbler_api" % cob.ipaddr
    print("Connecting to %s." % cobbler_url)
    server = xmlrpclib.Server(cobbler_url)
    token = server.login("cobbler","xcobbler")

    systems = [Node(config, node) for node in NODES_RANGE]

    for system in systems:
        cobbler_addsystem(server, token, system, profile, hostip)

def main():
    outpre = "libvirt-cobbler-"
    cfg_file = "settings.cfg"

    if len(sys.argv) == 1:
        print(
            "Usage: setup.py action\n"
            "action one of: libvirt-setup, cobbler-setup")
        sys.exit(1)

    config = yaml_loadf(cfg_file)

    if sys.argv[1] == "libvirt-setup":
        libvirt_setup(config)
    elif sys.argv[1] == "cobbler-setup":
        cobbler_setup(config)

if __name__ == '__main__':
    main()
