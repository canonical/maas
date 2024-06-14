# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Form utilities."""


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
    return "'{}' is not a valid {}.  It should be one of: {}.".format(
        "%(value)s",
        choice_of_what,
        ", ".join("'%s'" % name for name, value in valid_choices),
    )


def get_QueryDict(params: dict, mutable: bool = True) -> QueryDict:
    """Convert `params` to a `QueryDict`."""
    query_dict = QueryDict("", mutable=mutable)
    for k, v in params.items():
        if isinstance(v, list):
            query_dict.setlist(k, v)
        else:
            query_dict[k] = v
    return query_dict


def set_form_error(form, field_name, error_value):
    """Set an error on a form's field.

    This utility method encapsulates Django's arguably awkward way
    of settings errors inside a form's clean()/is_valid() method.  This
    method will override any previously-registered error for 'field_name'.
    """
    # Hey Django devs, this is a crap API to set errors.
    form.errors.setdefault(field_name, []).extend(
        form.error_class([error_value])
    )
