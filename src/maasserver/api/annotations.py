# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
This idea borrows heavily from apidocjs. It's been simplified
and adapted for a python environment where in-place dynamic output is
needed based on a docstring and template.

The APIDocstringParser accepts docstrings for parsing and
returns a dictionary containing the values given with
embedded annoations of the form:

    @description arbitrary text
    @description-title arbitrary text

    OR

    @tag (type) "id-or-name" [opt1=foo,opt2=bar] arbitrary text
    @tag-example "id-or-name" [opt1=foo,opt2=bar] arbitrary text

@tag can be:

    @param: Describes an API parameter
    @param-example: A typical param
    @success: Describes a successful API return value
    @success-example: A typical successful return value
    @error: Describes an error state
    @error-example: A typical error return value

"type" can be:

    string: a unicode string
    int: an integer
    json: a json object
    boolean: True or False
    float: a floating point number
    url-string: a URL-encoded string
    http-status-code: an HTTP status code
    content: content served via a MAAS server

"id-or-name" can be any string that doesn't contain spaces.

Arbitrary text can contain any string with or without spaces.
In most cases, formatting is preserved when presenting output.

With the exception of the description tag, docstrings can
contain as many tags as necessary to describe an API call.

Descriptions:

Description annotations can be interpreted in a couple of ways:

  Implicit titles:
    In this scenario, the first line of a description field can be
    considered a 'title' of sorts. The CLI help, for example, follows
    this convention.

  Explicit title:
    The APIDocstringParser also contains support for an explicit
    title (@description-title), which the CLI-help code should
    honor if present.

Example tags:

For an example tag to be successfully associated with
a tag, the name or ID fields of the annotations must match:

    E.g.

    @param (string) "p1" Some text.
    @param-example "p1" foobarbaz

In this case, param "p1" and param-example "p1" will be
paired together in the output dictionary.

Options:

The [required=true|false] option is a requirement for the
@param tag.

Example tags can either include formatted examples inline:

@success-example "some-name"
    {
        "name": "value"
    }

Or reference an example key for lookup in a JSON database
in the examples directory based on the URI. For example:

    /MAAS/api/2.0/zone/{name}/ -> examples/zones.json
    /MAAS/api/2.0/zones/{name}/ -> examples/zones.json

Use the "exkey" to do this:

@success-example "some-name" [exkey=unique-key] ignored text

Where:

examples/zones.json contains:

{
    ...
    "unique-key": { ...some JSON object...},
    ...
}

In addition, param tags support the "formatting" option:

    [formatting=true|false]

This can be used inside a Tempita template to output formatted
param descriptions.

Notes:

This class is typically used in conjunction with the
APITemplateRenderer class (templates.py).

OUTPUT:

    The get_dict class member will return a dictionary. Here is an
    example:

    {
      "http_method": "GET",
      "uri": "/MAAS/api/2.0/myuri/{foo}/",
      "operation": "arg1=foo&arg2=bar",
      "description-title": "A brief, title-like description",
      "description": "Some longer description.",
      "description_stripped": "description without formatting",
      "params": [
        {
          "name": "param",
          "type": "string",
          "description": "Some description.\n",
          "options": {
              "required": "true",
              "testopt2": "bar"
          },
          "example": " my param example\n",
        }
      ],
      "successes": [
        {
          "name": "success1",
          "type": "json",
          "description": "A JSON object. See example for more detail.\n",
          "options": {
              "testopt1": "foo"
          },
          "example": "\n    {\n        \"key1\":10    }\n",
        }
      ],
      "errors": [
        {
          "name": "403",
          "type": "http-header",
          "description": "If user is not authorized.\n",
          "options": {
              "testopt1": "bar"
              "some-opt": "foobar"
          },
          "example": "\n    { \"not authorized\" }",
        }
      ]
    }

NOTES:
    1. We don't pre-compile the regexes and instead rely on
    Python's internal caching. This wouldn't be hard to
    change if a speed improvement is needed.
"""

import json
import os
import re
from textwrap import indent


class APIDocstringParser:
    allowed_tags = [
        "description",
        "description-title",
        "param",
        "param-example",
        "success",
        "success-example",
        "error",
        "error-example",
    ]

    allowed_types = [
        "string",
        "url-string",
        "int",
        "content",
        "http-status-code",
        "json",
        "boolean",
        "float",
    ]

    @staticmethod
    def is_annotated_docstring(docstring):
        """Returns True if a given docstring contains a known tag."""
        for tag in APIDocstringParser.allowed_tags:
            if docstring.find("@%s" % tag) != -1:
                return True

        return False

    @staticmethod
    def is_valid_type(ttype):
        """Returns True if type is valid, False if not."""
        return ttype in APIDocstringParser.allowed_types

    def _get_pretty_type_string(self, ttype):
        """Returns a version suitable for printing

        Capitalizes like a title and replaces hyphens
        with spaces.
        """

        if ttype == "url-string":
            return "URL String"
        elif ttype == "http-status-code":
            return "HTTP Status Code"
        elif ttype == "json":
            return "JSON"

        return ttype.title().replace("-", " ")

    def _warn_on_invalid_type(self, ttype, tname, tag):
        """Issues a warning if type is not valid."""

        if not self.is_valid_type(ttype):
            self._warn(
                "%s is not a valid type for %s in '%s' tag"
                % (ttype, tname, tag)
            )

    def _warn(self, msg, context=""):
        """Collects a given warning for later use."""

        if context != "":
            context = indent("in:\n%s" % context, "    ")

        self.warnings = self.warnings + "API_WARNING: {}\n\n{}".format(
            msg,
            context,
        )

    def _syntax_error(self, msg, context=""):
        """Collects a given syntax error for later use."""

        if context != "":
            context = indent("in:\n%s" % context, "    ")

        self.warnings = self.warnings + "API_SYNTAX_ERROR: {}\n\n{}".format(
            msg,
            context,
        )

    def _is_name_in_tags(self, name, tags):
        """Tries to find the given name value in the tags.

        Returns True if the given tags contain a tag with the
        key 'name' and value name.
        """
        for tag in tags:
            if tag["name"] == name:
                return True

        return False

    def _warn_on_orphaned_examples(self, tag_cat, tags, examples):
        """Issues warning if orphaned examples are found

        Params, successes and errors can have examples associated
        with them, but they are not required. We need to know if
        a user intended to include an example and made a mistake
        naming it, thereby stranding the example with no associated
        tag.

        In other words, not every tag should have an example, but
        every example should have a tag.
        """
        for example in examples:
            if not self._is_name_in_tags(example["name"], tags):
                self._warn(
                    "Couldn't find matching tag named '%s' in "
                    "%s tags." % (example["name"], tag_cat)
                )

    def _get_named_example_for_named_tag(self, tag_cat, tag_name, examples):
        """Maps examples to associated named tags.

        Given a tag's name -- "tag_name" -- this function searches
        through a list of associated example tags to find one with
        the same name. tag_cat is used as a clue in case a name
        doesn't match.

        E.g.
            @param (string) "param_id" some description
            @param-example "param_id" param example

        The text 'param example' will be added to param_id's example
        key as a value.

        A warning is collected if the name is empty.
        """

        for example in examples:
            if example["name"] == tag_name:
                if tag_name == "":
                    self._warn(
                        "Mapped empty name to an empty name. Did you "
                        "forget to name your example to match a '%s'?\nThis "
                        "can result in double examples." % tag_cat
                    )
                return example

        return {}

    def _get_options_dict(self, options_string):
        """Converts a string of key, value pairs into a dictionary.

        The options field of an annotation can hold any tag-specific
        instructions to be added later on. For example, the following
        might indicate to use bold when outputting:

        @tag (type) "tagid" [format=bold] some description
        """
        # hasopt1=foo,hasopt2=bar
        d = {}

        if options_string != "":
            for opt in options_string.split(","):
                key, val = opt.split("=")
                if key in d:
                    self._warn(
                        "Found duplicate key '%s' in options '%s'"
                        % (key, options_string)
                    )
                d[key] = val

        return d

    def _map_named_tags_to_named_examples(self, tag_cat, tags, examples):
        """Maps a list of tags to a list of examples.

        Given a list of similar tags (e.g. params) and associated examples
        (e.g. param-examples), this function maps an example to a tag via
        the tag's name key.

        When a match is found, the example's description field becomes the
        tag's example field.
        """
        return_list = []
        for tag in tags:
            example = self._get_named_example_for_named_tag(
                tag_cat, tag["name"], examples
            )
            if example:
                # We default to the description for this example given in the
                # docstring.
                example_desc = example["description"]

                # If the user has given options, check for the presence of
                # 'exkey'.
                example_options = example["options"]
                if example_options is not None and "exkey" in example_options:
                    example_options_exkey = example_options["exkey"]
                    # If the examples db is empty, since we have an exkey,
                    # we need to warn.
                    if self.examples_db is None:
                        self._warn(
                            "Found 'exkey'='%s' in example named '%s', but "
                            "the examples database is empty."
                            % (example_options_exkey, example["name"])
                        )
                    elif example_options_exkey in self.examples_db:
                        # Use indent=4 in order to tell json to format
                        # the outgoing string as opposed to keeping it on
                        # one line.
                        example_desc = json.dumps(
                            self.examples_db[example["options"]["exkey"]],
                            indent=4,
                        )
                    else:
                        self._warn(
                            "Found 'exkey'='%s' in example named '%s', "
                            "but found no corresponding entry in the the "
                            "examples database."
                            % (example["options"]["exkey"], example["name"])
                        )

                # example will contain either the description provided in the
                # docstring as is, or it will have been replaced with an
                # entry from the examples_db
                tag["example"] = example_desc

            else:
                tag["example"] = ""

            return_list.append(tag)

        return return_list

    def _clear_docstring_vars(self):
        # Chunk of plain-text, usually single-line
        self.description_title = ""
        # Chunk of plain-text, multi-line
        self.description = ""
        # params are name, type, description, and example
        # (populated after the fact), multiline
        self.params = []
        # examples are name (should match a param name),
        # type, description, multiline
        self.examples = []
        # Success name, type and description, multiline
        self.successes = []
        # Success example, name (should match success name),
        # description, multi-line
        self.success_examples = []
        # Error description, name, type, description, multi-line
        self.errors = []
        # Error example, name (should match error name),
        # description, multi-line
        self.error_examples = []
        # Clear out any collected warnings
        self.warnings = ""
        # Clear the examples database
        self.examples_db = None

    # Strips multiple inline spaces, all newlines, and
    # leading and trailing spaces
    def _strip_spaces_and_newlines(self, s):
        s_stripped = re.sub(r"\s{2,}", " ", s)
        s_stripped = re.sub(r"\n", " ", s_stripped)

        return s_stripped.rstrip().lstrip()

    def _create_tag_dict(self, tname, ttype, opts, desc):
        desc_stripped = self._strip_spaces_and_newlines(desc)

        d = {
            "name": tname,
            "type": self._get_pretty_type_string(ttype),
            "description": desc,
            "description_stripped": desc_stripped,
            "options": self._get_options_dict(opts),
            "example": "",
        }
        return d

    def _val_is_true_or_false(self, val):
        """Return False if lowercased val is not true or false"""
        return val.lower() in ("true", "false")

    def _check_param_tag(self, tag_dict, tag_name):
        """Checks param tag dict for syntax problems.

        Check the given param tag's dictionary to make sure there are no
        problems with the options, such as a missing required option or
        a bad formatted option.

        Returns an array of warning strings or None if there are no
        problems.
        """
        warns = []
        options = tag_dict["options"]

        # Check required option first
        if "required" not in options:
            warns.append("Option key 'required' not found in %s." % tag_name)
        else:
            if not self._val_is_true_or_false(options["required"]):
                warns.append(
                    "Option key 'required' must be 'true' or 'false' in %s."
                    % tag_name
                )

        # Now check for formatting option
        if "formatting" in options:
            if not self._val_is_true_or_false(options["formatting"]):
                warns.append(
                    "Option key 'formatting' must be 'true' or 'false' in"
                    "%s." % tag_name
                )

        return None if len(warns) == 0 else warns

    def _process_docstring_tag(self, tag, tname, ttype, opts, desc, docstring):
        """Processes parsed tag information in contextual way.

        Given a tag, tag name, tag type, options, description and the original
        docstring, process the separate bits of info into a coherent dictionary
        based on what kind of tag is found.

        This function will also warn if something looks fishy, like if a
        developer puts options in a description tag.
        """

        # @description-title
        if tag == "description-title":
            if self.description_title != "":
                self._warn(
                    "Found another description-title field. Will "
                    "overwrite the original.",
                    docstring,
                )

            if ttype != "" or tname != "" or opts != "":
                self._warn(
                    "type, name, and options are not "
                    "available for the description-title tag.",
                    docstring,
                )

            self.description_title = self._strip_spaces_and_newlines(desc)
        #
        # @description
        #
        elif tag == "description":
            if self.description != "":
                self._warn(
                    "Found another description field. "
                    "Will overwrite the original.",
                    docstring,
                )

            if ttype != "" or tname != "" or opts != "":
                self._warn(
                    "type, name, and options are not "
                    "available for the description tag.",
                    docstring,
                )

            self.description = desc
        #
        # @param
        #
        elif tag == "param":
            tag_dict = self._create_tag_dict(tname, ttype, opts, desc)

            warns = self._check_param_tag(tag_dict, tname)
            if warns is not None:
                for warn_str in warns:
                    self._warn(warn_str, docstring)

            self._warn_on_invalid_type(ttype, tname, "param")

            self.params.append(tag_dict)
        #
        # @param-example
        #
        elif tag == "param-example":
            self.examples.append(
                self._create_tag_dict(tname, ttype, opts, desc)
            )
        #
        # @success
        #
        elif tag == "success":
            self.successes.append(
                self._create_tag_dict(tname, ttype, opts, desc)
            )

            self._warn_on_invalid_type(ttype, tname, "success")
        #
        # @success-example
        #
        elif tag == "success-example":
            self.success_examples.append(
                self._create_tag_dict(tname, ttype, opts, desc)
            )
        #
        # @error
        #
        elif tag == "error":
            self.errors.append(self._create_tag_dict(tname, ttype, opts, desc))

            self._warn_on_invalid_type(ttype, tname, "error")
        #
        # @error-example
        #
        elif tag == "error-example":
            self.error_examples.append(
                self._create_tag_dict(tname, ttype, opts, desc)
            )
        #
        # Fall through to warning message
        #
        else:
            self._syntax_error("Unknown tag: %s" % tag, docstring)

    def _sanity_check_tag_and_get_warning(self, tag, tname, ttype, opts, desc):
        """Returns a string warning if there are semantic issues.

        Based on the tag, we look for the other things to
        be present. E.g. if the tag is @description and there
        is no actual description, that's likely an issue.
        """

        # Empty descriptions are never allowed for any tag
        if desc.strip() == "":
            return "%s had an empty description" % tag

        if tag == "param":
            if tname == "" or ttype == "" or desc == "":
                return "a param tag may be incomplete"
        elif tag == "param-example":
            if tname == "" or desc == "":
                return "a param-example tag may be incomplete"
        elif tag == "success":
            if tname == "" or ttype == "" or desc == "":
                return "a success tag may be incomplete"
        elif tag == "success-example":
            if tname == "" or desc == "":
                return "a success-example tag may be incomplete"
        elif tag == "error":
            if tname == "" or ttype == "" or desc == "":
                return "an error tag may be incomplete"
        elif tag == "error-example":
            if tname == "" or desc == "":
                return "an error-example tag may be incomplete"

        return ""

    def _get_operation_from_uri(self, uri):
        """Parses out an operation name from a given URI.

        Given, for example, /MAAS/api/2.0/resourcepool/{id}/, this
        function returns "resourcepool".
        """
        m = re.search(r"/MAAS/api/[0-9]+\.[0-9]+/([a-z\-]+)/", uri)
        if m:
            return m.group(1)

        # Note that *not* finding an operation in a URI is normal
        # and acceptable because sometimes we're parsing a docstring
        # that the user hasn't associated with a URI.

        return ""

    def _load_nodes_examples_dict(self):
        """Returns a dictionary containing 'nodes' examples data.

        Since many API objects inherit from nodes (e.g. machines, devices) we
        always load nodes examples to prevent duplicating data.

        If examples/nodes.json cannot be found, we warn, which will prevent
        the unit tests from completing normally, but we return an empty
        dictionary so the code can continue.
        """
        nodes_examples = {}

        json_file = "%s/examples/nodes.json" % os.path.dirname(__file__)

        if not os.path.isfile(json_file):
            self._warn("examples/nodes.json not found.")
        else:
            with open(json_file) as ex_db_file:
                nodes_examples = json.load(ex_db_file)

        return nodes_examples

    def _get_examples_dict(self, uri):
        """Returns a dictionary containing examples data

        Given an operation string like "zone" or "zones", this function tries
        to open and slurp in the JSON of a matching file in the api/examples
        directory (e.g. tags.json). Example objects look like this:

            "uniquekey": {
                ... any JSON object ...
            }

        This function will always return at least nodes examples data.
        """
        examples = self._load_nodes_examples_dict()

        operation = self._get_operation_from_uri(uri)
        if operation == "" or operation == "nodes" or operation == "node":
            return examples

        # First, try the operation string as is:
        json_file = "{}/examples/{}.json".format(
            os.path.dirname(__file__),
            operation,
        )

        if not os.path.isfile(json_file):
            # Not available, so try adding an 's' to make it plural
            json_file = "{}/examples/{}s.json".format(
                os.path.dirname(__file__),
                operation,
            )

            if not os.path.isfile(json_file):
                # No examples found so return base set
                return examples

        with open(json_file) as ex_db_file:
            operation_examples = json.load(ex_db_file)
            examples.update(operation_examples)

        return examples

    def parse(self, docstring, http_method="", uri="", operation=""):
        """State machine that parses annotated API docstrings.

        This function parses a docstring by looking for a series of
        structured text blocks that follow a basic format:

            @tag (type) "name" [key1=val1,...,keyn=valn] description

        In order to retain basic formatting, it splits the
        docstring by newline and space while retaining both.

        The only required argument is 'docstring'. When rendering the
        API docstrings for the web, we use the optional arguments. For
        CLI help and testing, we don't need them.
        """
        from enum import Enum

        class ParseState(Enum):
            TAG = 0
            TYPE = 1
            NAME = 2
            OPTS = 3
            DESC = 4

        # Reset the state machine with the given variables so
        # we can reuse the same APIParseDocstring class instance
        # for multiple runs over many docstrings, rather than
        # instantiating a new class over and over.
        #
        # E.g.
        #     ap = APIDocstringParser()
        #     for docstring in all_docstrings:
        #         ap.parse(m, u, o, docstring)
        #
        self.http_method = http_method
        self.uri = uri
        self.operation = operation
        self._clear_docstring_vars()

        # Fetch and build a dictionary containing examples associated with
        # the given URI (if any)
        self.examples_db = self._get_examples_dict(uri)

        # Init parse state
        ps = ParseState.TAG

        # These help us to remember state as we parse docstrings
        tag = ""
        ttype = ""
        tname = ""
        opts = ""
        desc = ""

        # Use an indexed array so we can simulate a "put back" operation for
        # a one-word lookahead. Split on space (or repeated space) as well as
        # newlines and keep the split chars so indentation will be kept intact.
        words = re.split(r"(\s+|\n)", docstring)
        max_idx = len(words)
        idx = 0

        done = False
        while not done:
            word = words[idx]

            # Looking for a tag -- @tag
            if ps == ParseState.TAG:
                m = re.search(r"@([a-z\-]+)", word)
                if m:
                    tag = m.group(1)
                    ps = ParseState.TYPE
                else:
                    self._syntax_error(
                        "expecting annotation tag. Found '%s' "
                        "' instead." % word,
                        docstring,
                    )

            # Looking for a type -- (type)
            elif ps == ParseState.TYPE:
                m = re.search(r"\(([a-zA-Z0-9\-_]+)\)", word)
                if m:
                    ttype = m.group(1)
                    ps = ParseState.NAME
                elif not re.search(r"^[\s]+$", word):
                    ps = ParseState.NAME
                    # Put the word back
                    idx -= 1

            # Looking for a name -- "name"/'name'
            elif ps == ParseState.NAME:
                m = re.search(r"[\"\']([a-zA-Z0-9\-_{}]+)[\"\']", word)
                if m:
                    tname = m.group(1)
                    ps = ParseState.OPTS
                elif not re.search(r"^[\s]+$", word):
                    ps = ParseState.OPTS
                    # Put the word back
                    idx -= 1

            # Looking for options -- [options]
            elif ps == ParseState.OPTS:
                m = re.search(r"\[([a-zA-Z0-9\-_=\/;,\.~]+)\]", word)
                if m:
                    opts = m.group(1)
                    ps = ParseState.DESC
                elif not re.search(r"^[\s]+$", word):
                    ps = ParseState.DESC
                    # Put the word back
                    idx -= 1

            # Looking for description text -- any text
            elif ps == ParseState.DESC:
                # If we stumble onto another annotation, we put back the word
                # by decreasing the index so the next iteration of the loop
                # will look at this word with a different state active.
                if word.find("@") != -1:
                    idx -= 1
                    ps = ParseState.TAG

                    warn = self._sanity_check_tag_and_get_warning(
                        tag, tname, ttype, opts, desc
                    )
                    if warn != "":
                        self._warn(warn, docstring)
                    self._process_docstring_tag(
                        tag, tname, ttype, opts, desc, docstring
                    )

                    tname = ""
                    ttype = ""
                    desc = ""
                    opts = ""

                else:
                    desc += word

            idx += 1
            if idx >= max_idx:
                done = True

        warn = self._sanity_check_tag_and_get_warning(
            tag, tname, ttype, opts, desc
        )
        if warn != "":
            self._warn(warn, docstring)
        self._process_docstring_tag(tag, tname, ttype, opts, desc, docstring)

    def get_dict(self):
        """Returns a dictionary based on the collected pieces."""

        d = {}

        d["http_method"] = self.http_method
        d["uri"] = self.uri
        d["operation"] = self.operation
        d["description_title"] = self.description_title
        d["description"] = self.description
        d["params"] = self._map_named_tags_to_named_examples(
            "param", self.params, self.examples
        )
        d["successes"] = self._map_named_tags_to_named_examples(
            "success", self.successes, self.success_examples
        )
        d["errors"] = self._map_named_tags_to_named_examples(
            "error", self.errors, self.error_examples
        )

        # The user might have examples that do not have corresponding
        # tags.
        self._warn_on_orphaned_examples("params", self.params, self.examples)
        self._warn_on_orphaned_examples(
            "successes", self.successes, self.success_examples
        )
        self._warn_on_orphaned_examples(
            "errors", self.errors, self.error_examples
        )

        # We must add warnings last because they are populated
        # in _map_list_to_examples
        d["warnings"] = self.warnings

        return d
