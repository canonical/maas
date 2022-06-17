# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Monkey patch for the MAAS region server, with code for region server patching.
"""


from collections import OrderedDict

from twisted.web import http
import yaml

from provisioningserver.monkey import add_patches_to_twisted


def fix_ordereddict_yaml_representer():
    """Fix PyYAML so an OrderedDict can be dumped."""

    def dumper(dumper, data):
        return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())

    yaml.add_representer(OrderedDict, dumper, Dumper=yaml.Dumper)
    yaml.add_representer(OrderedDict, dumper, Dumper=yaml.SafeDumper)


OriginalRequest = http.Request


class PatchedRequest(OriginalRequest):
    def write(self, data):
        if self.finished:
            raise RuntimeError(
                "Request.write called on a request after "
                "Request.finish was called."
            )

        if self._disconnected:
            # Don't attempt to write any data to a disconnected client.
            # The RuntimeError exception will be thrown as usual when
            # request.finish is called
            return

        return OriginalRequest.write(self, data)


def fix_twisted_disconnect_write():
    """
    Patch twisted.web.http.Request to include the upstream fix

    See https://github.com/twisted/twisted/commit/169fd1d93b7af06bf0f6893b193ce19970881868
    """

    http.Request = PatchedRequest


def add_patches():
    add_patches_to_twisted()
    fix_ordereddict_yaml_representer()
    fix_twisted_disconnect_write()
