# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""
This class is typically used in conjunction with the
APIDocstringParser class to populate a template with
the results of a fully-parsed annotated docstring.

A typical use is:

.
.
api_ds_parser = APIDocstringParser()
api_template_renderer = APITemplateRenderer()

for function_def in function_defs:
  docstring = ast.get_docstring(function_def)
  if docstring:
    api_ds_parser.parse("GET",
        "/myuri/{path_param}/",
            "op=details&foo=bar", docstring)
    print(
        api_template_renderer.apply_template("./tmpl-apidoc.md",
            api_ds_parser))
.
.

"""

__all__ = [
    "APITemplateRenderer",
]

import os

import jinja2


class APITemplateRenderer:
    # A simple path-based loader
    class PathLoader(jinja2.BaseLoader):
        def __init__(self):
            self.path = ""

        def get_source(self, environment, template):
            path = template
            if not os.path.exists(path):
                raise jinja2.TemplateNotFound(template)
            mtime = os.path.getmtime(path)
            with open(path) as f:
                source = f.read()
            return source, path, lambda: mtime == os.path.getmtime(path)

    def __init__(self):
        # Create a simple loader that will simply load a template
        # from a given path.
        self.loader = APITemplateRenderer.PathLoader()

        # Set up a simple jinja2 environment
        # autoescape=jinja2.select_autoescape(['html']),
        self.env = jinja2.Environment(
            loader=self.loader,
            trim_blocks=True,
            lstrip_blocks=True
        )

    # Applies the given jinja2 template on path using the
    # the dictionary supplied by the given APIDocstringParser
    def apply_template(self, path, doc_string_parser):
        # Load the given template
        template = self.env.get_template(path)

        d = doc_string_parser.get_dict()

        # Render the template
        return template.render(d)
