# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Restful MAAS API.

This is the documentation for the API that lets you control and query MAAS.
The API is "Restful", which means that you access it through normal HTTP
requests.


API versions
````````````

At any given time, MAAS may support multiple versions of its API.  The version
number is included in the API's URL, e.g. /api/2.0/

For now, 2.0 is the only supported version.

The current API version number can be retrieved by issuing a GET to
"/api/version/". Accessing an old or unknown API version URL will result in a
"410 GONE" being returned, along with a descriptive error message. Both the
error message and the api version are returned as plaintext.


HTTP methods and parameter-passing
``````````````````````````````````

The following HTTP methods are available for accessing the API:

* GET (for information retrieval and queries),
* POST (for asking the system to do things),
* PUT (for updating objects), and
* DELETE (for deleting objects).

All methods except DELETE may take parameters, but they are not all passed in
the same way.  GET parameters are passed in the URL, as is normal with a GET:
"/item/?foo=bar" passes parameter "foo" with value "bar".

POST and PUT are different.  Your request should have MIME type
"multipart/form-data"; each part represents one parameter (for POST) or
attribute (for PUT).  Each part is named after the parameter or attribute it
contains, and its contents are the conveyed value.

All parameters are in text form.  If you need to submit binary data to the
API, don't send it as any MIME binary format; instead, send it as a plain text
part containing base64-encoded data.

Most resources offer a choice of GET or POST operations.  In those cases these
methods will take one special parameter, called `op`, to indicate what it is
you want to do.

For example, to list all machines, you might GET "/MAAS/api/2.0/machines/".
"""

from copy import deepcopy
from functools import partial
from inspect import getdoc
from io import StringIO
import json
import os
import sys
from textwrap import dedent

from django.http import HttpResponse

from maasserver.api.annotations import APIDocstringParser
from maasserver.api.doc import (
    find_api_resources,
    generate_api_docs,
    generate_pod_types_doc,
    generate_power_types_doc,
    get_api_description,
)
from maasserver.api.templates import APITemplateRenderer
from maasserver.utils import build_absolute_uri

# Title section for the API documentation.  Matches in style, format,
# etc. whatever render_api_docs() produces, so that you can concatenate
# the two.
api_doc_title = dedent(
    """
    .. _maas-api:

    ========
    MAAS API
    ========
    """.lstrip("\n")
)


def render_api_docs():
    """Render ReST documentation for the REST API.


    This module's docstring forms the head of the documentation; details of
    the API methods follow.

    :return: Documentation, in ReST, for the API.
    :rtype: :class:`unicode`
    """
    from maasserver import urls_api as urlconf

    module = sys.modules[__name__]
    output = StringIO()
    line = partial(print, file=output)

    line(getdoc(module))
    line()
    line()
    line("Operations")
    line("``````````")
    line()

    def export_key(export):
        """Return a sortable key for an export.

        `op` is often `None`, which cannot be compared to non-`None`
        operations.
        """
        (http_method, op), function = export
        if op is None:
            return http_method, "", function
        else:
            return http_method, op, function

    annotation_parser = APIDocstringParser()
    templates = APITemplateRenderer()
    resources = find_api_resources(urlconf)
    for doc in generate_api_docs(resources):
        uri_template = doc.resource_uri_template
        exports = doc.handler.exports.items()
        # Derive a section title from the name of the handler class.
        section_name = doc.handler.api_doc_section_name
        line(section_name)
        line("=" * len(section_name))
        # Note:
        # The following dedent is useless in the following situation:
        #
        # def somefunc(foo)
        #     """No indent here
        #
        #     Here, there is an indent, so dedent doesn't do
        #     anything.
        #    """
        #
        # This fixes the problem:
        #
        # def somefunc(foo)
        #     """
        #     Indent here
        #
        #     Now dedent works because the entire docstring appears
        #     to be indented.
        #    """
        #
        # This also works because the dedent version is the same
        # as the non-dented version:
        #
        # def somefunc(foo)
        #     """No indent here"""
        #
        line(dedent(doc.handler.__doc__).strip())
        line()
        line()
        for (http_method, op), function in sorted(exports, key=export_key):
            operation = " op=%s" % op if op is not None else ""
            subsection = (
                f"<code>{http_method} {uri_template}{operation}</code>"
            )
            docstring = getdoc(function)
            if docstring is not None:
                if APIDocstringParser.is_annotated_docstring(docstring):
                    operation = "op=%s" % op if op is not None else ""
                    annotation_parser.parse(
                        docstring, http_method, uri_template, operation
                    )
                    line(
                        templates.apply_template(
                            os.path.dirname(__file__) + "/tmpl-apidoc.rst",
                            annotation_parser,
                        )
                    )
                else:
                    line(".. raw:: html")
                    line()
                    line("  <details>")
                    line(f"  <summary>{subsection}</summary>")
                    line()
                    for docline in dedent(docstring).splitlines():
                        if docline.strip() == "":
                            # Blank line.  Don't indent.
                            line()
                        else:
                            # Print documentation line, indented.
                            line(docline)
                    line()
                    line(".. raw:: html")
                    line()
                    line("  </details>")
                    line()
                line()
            else:
                line(".. raw:: html")
                line()
                line(f"  <p>{subsection}</p>\n")
                line()

    line()
    line()
    line(generate_power_types_doc())
    line()
    line()
    line(generate_pod_types_doc())

    return output.getvalue()


def describe(request):
    """Render a description of the whole MAAS API.

    :param request: A "related" HTTP request. This is used to derive the URL
        where the client expects to see the MAAS API.
    :return: An `HttpResponse` containing a JSON description of the whole MAAS
        API. Links to the API will use the same scheme and hostname that the
        client used in `request`.
    """
    description = deepcopy(get_api_description())
    # Make all URIs absolute. Clients - and the command-line client in
    # particular - expect that all handler URIs are absolute, not just paths.
    # The handler URIs returned by _describe_resource() are relative paths.
    absolute = partial(build_absolute_uri, request)
    for resource in description["resources"]:
        for handler_type in ("anon", "auth"):
            handler = resource[handler_type]
            if handler is not None:
                handler["uri"] = absolute(handler["path"])
    # Return as a JSON document.
    return HttpResponse(
        json.dumps(description, sort_keys=True),
        content_type="application/json",
    )
