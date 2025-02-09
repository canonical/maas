# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Monkey patch for the MAAS region server, with code for region server patching.
"""

from collections import OrderedDict

import yaml

from provisioningserver.monkey import add_patches_to_twisted


def fix_ordereddict_yaml_representer():
    """Fix PyYAML so an OrderedDict can be dumped."""

    def dumper(dumper, data):
        return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())

    yaml.add_representer(OrderedDict, dumper, Dumper=yaml.Dumper)
    yaml.add_representer(OrderedDict, dumper, Dumper=yaml.SafeDumper)


def add_patches():
    add_patches_to_twisted()
    fix_ordereddict_yaml_representer()
