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

import tempita


class APITemplateRenderer:
    # Applies the given tempita template on path using the
    # the dictionary supplied by the given APIDocstringParser
    def apply_template(self, path, doc_string_parser):
        # Load the given template
        template = tempita.Template.from_filename(path, encoding="utf-8")

        d = doc_string_parser.get_dict()

        # Render the template
        return template.substitute(d)
