# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Form utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'compose_invalid_choice_text',
    'get_QueryDict',
]

from django.http import QueryDict


def compose_invalid_choice_text(choice_of_what, valid_choices):
    """Compose an "invalid choice" string for form error messages.

    This returns a template string that is intended to be used as the
    argument to the 'error_messages' parameter in a Django form.

    :param choice_of_what: The name for what the selected item is supposed
        to be, to be inserted into the error string.
    :type choice_of_what: unicode
    :param valid_choices: Valid choices, in Django choices format:
        (name, value).
    :type valid_choices: sequence
    """
    return "'%s' is not a valid %s.  It should be one of: %s." % (
        "%(value)s",
        choice_of_what,
        ", ".join("'%s'" % name for name, value in valid_choices),
    )


def get_QueryDict(params):
    """Convert `params` to a `QueryDict`."""
    query_dict = QueryDict('', mutable=True)
    for k, v in params.items():
        if isinstance(v, list):
            query_dict.setlist(k, v)
        else:
            query_dict[k] = v
    return query_dict
