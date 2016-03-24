# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Sphinx extension that produces a JSON file with details about all the
available versions of the MAAS documentation.
"""

import json
import os

import sphinx

# The name of the version JSON file being written by this extension.
VERSION_FILE = '_static/versions.json'

# The name of the config option used to get the list of the availables
# versions.
VERSION_CONFIG_NAME = b'doc_versions'


def write_versions_file(app, exception):
    # The creation of the versions file is only needed when building
    # the documentation and it assumes the directory 'docs/_static' exists:
    # Create the versions file only when Sphinx is building the documentation.
    if not isinstance(app.builder, sphinx.builders.html.StandaloneHTMLBuilder):
        return

    import conf  # Our configuration with custom values.
    versions_file = os.path.join(app.outdir, VERSION_FILE)
    with open(versions_file, 'w', encoding="ascii") as f:
        f.write(json.dumps(conf.doc_versions))


def setup(app):
    app.add_config_value(VERSION_CONFIG_NAME, {}, False)
    app.connect('build-finished', write_versions_file)
