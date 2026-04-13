#!/usr/bin/env python3
#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Sphinx extension to automatically generate CLI documentation.

This extension runs during the Sphinx build process and automatically
generates the API documentation by calling generate_cli_docs.py, which
in turn generates the CLI documentation markdown file.

The generated file is created before Sphinx processes the markdown files,
ensuring the API documentation is always up-to-date.
"""

from pathlib import Path
import sys

from sphinx.util import logging

logger = logging.getLogger(__name__)


def generate_cli_docs(app, config):
    """Generate API documentation during Sphinx build.

    This function is called during the config-inited phase of Sphinx,
    which happens before any source files are read.
    """
    rtd_docs_dir = Path(app.srcdir)
    scripts_dir = rtd_docs_dir / "_scripts"

    generate_script = scripts_dir / "generate_cli_docs.py"

    if not generate_script.exists():
        logger.warning(
            f"API docs generator script not found: {generate_script}"
        )
        return

    sys.path.insert(0, str(scripts_dir))

    try:
        import generate_cli_docs as gen_module

        gen_module.generate_cli_docs()

    except Exception as e:
        logger.warning(f"Failed to generate API documentation: {e}")
        import traceback

        logger.warning(traceback.format_exc())


def setup(app):
    """Sphinx extension setup function.

    This function is called by Sphinx to register the extension.
    """
    app.connect("config-inited", generate_cli_docs)

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
