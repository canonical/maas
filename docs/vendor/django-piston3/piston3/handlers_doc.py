import re

from .doc import generate_doc
from .handler import handler_tracker


def generate_piston_documentation(app, docname, source):
    e = re.compile(r"^\.\. piston_handlers:: ([\w\.]+)$")
    old_source = source[0].split("\n")
    new_source = old_source[:]
    for line_nr, line in enumerate(old_source):
        m = e.match(line)
        if m:
            module = m.groups()[0]
            try:
                __import__(module)
            except ImportError:
                pass
            else:
                new_lines = []
                for handler in handler_tracker:
                    doc = generate_doc(handler)
                    new_lines.append(doc.name)
                    new_lines.append("-" * len(doc.name))
                    new_lines.append("::\n")
                    new_lines.append(
                        "\t" + doc.get_resource_uri_template() + "\n"
                    )
                    new_lines.append("Accepted methods:")
                    for method in doc.allowed_methods:
                        new_lines.append("\t* " + method)
                    new_lines.append("")
                    if doc.doc:
                        new_lines.append(doc.doc)
                new_source[line_nr : line_nr + 1] = new_lines

    source[0] = "\n".join(new_source)
    return source


def setup(app):
    app.connect("source-read", generate_piston_documentation)
