# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Sphinx extension that produces a JSON file with details about all the
available versions of the MAAS documentation.
"""


from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type


import os, json
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

    doc_versions = app.config.doc_versions
    versions_file = os.path.join(app.outdir, VERSION_FILE)
    with open(versions_file, 'wb') as f:
        f.write(json.dumps(doc_versions))


def setup(app):
    app.add_config_value(VERSION_CONFIG_NAME, {}, False)
    app.connect(b'build-finished', write_versions_file)
