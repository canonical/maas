#!/usr/bin/env python3
#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Sphinx extension to automatically generate API documentation.

This extension runs during the Sphinx build process and automatically
generates the API documentation by calling generate_api_docs.py, which
in turn generates the OpenAPI spec from source and creates the markdown file.

The generated file is created before Sphinx processes the markdown files,
ensuring the API documentation is always up-to-date.
"""

from pathlib import Path
import sys


def generate_api_docs(app, config):
    """Generate API documentation during Sphinx build.

    This function is called during the config-inited phase of Sphinx,
    which happens before any source files are read.
    """
    rtd_docs_dir = Path(app.srcdir)
    scripts_dir = rtd_docs_dir / "_scripts"

    generate_script = scripts_dir / "generate_api_docs.py"

    # Verify script exists
    if not generate_script.exists():
        app.warn(f"API docs generator script not found: {generate_script}")
        return

    # app.info("Generating API documentation...")

    # Add scripts directory to path and import the generator
    sys.path.insert(0, str(scripts_dir))

    try:
        # Import and call the generation function (not main, to avoid argparse)
        import generate_api_docs as gen_module

        # Call generate_docs directly with no arguments (auto-detect mode)
        gen_module.generate_docs()

        # app.info("✓ API documentation generated successfully!")
    except Exception as e:
        app.warn(f"Failed to generate API documentation: {e}")
        import traceback

        app.warn(traceback.format_exc())


def setup(app):
    """Sphinx extension setup function.

    This function is called by Sphinx to register the extension.
    """
    # Connect our generator to the config-inited event
    # This runs after configuration is loaded but before source files are read
    app.connect("config-inited", generate_api_docs)

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
