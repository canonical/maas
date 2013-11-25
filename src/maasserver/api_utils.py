# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for Piston-based MAAS APIs."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'extract_bool',
    'extract_oauth_key',
    'get_list_from_dict_or_multidict',
    'get_mandatory_param',
    'get_oauth_token',
    'get_optional_list',
    'get_overridden_query_dict',
    ]

from django.core.exceptions import ValidationError
from django.http import QueryDict
from formencode.validators import Invalid
from maasserver.exceptions import Unauthorized
from piston.models import Token


def extract_bool(value):
    """Extract a boolean from an API request argument.

    Boolean arguments to API requests are passed as string values: "0" for
    False, or "1" for True.  This helper converts the string value to the
    native Boolean value.

    :param value: Value of a request parameter.
    :type value: unicode
    :return: Boolean value encoded in `value`.
    :rtype bool:
    :raise ValueError: If `value` is not an accepted encoding of a boolean.
    """
    assert isinstance(value, unicode)
    if value == '0':
        return False
    elif value == '1':
        return True
    else:
        raise ValueError("Not a valid Boolean value (0 or 1): '%s'" % value)


def get_mandatory_param(data, key, validator=None):
    """Get the parameter from the provided data dict or raise a ValidationError
    if this parameter is not present.

    :param data: The data dict (usually request.data or request.GET where
        request is a django.http.HttpRequest).
    :param data: dict
    :param key: The parameter's key.
    :type key: unicode
    :param validator: An optional validator that will be used to validate the
         retrieved value.
    :type validator: formencode.validators.Validator
    :return: The value of the parameter.
    :raises: ValidationError
    """
    value = data.get(key, None)
    if value is None:
        raise ValidationError("No provided %s!" % key)
    if validator is not None:
        try:
            return validator.to_python(value)
        except Invalid as e:
            raise ValidationError("Invalid %s: %s" % (key, e.msg))
    else:
        return value


def get_optional_list(data, key, default=None):
    """Get the list from the provided data dict or return a default value.
    """
    value = data.getlist(key)
    if value == []:
        return default
    else:
        return value


def get_list_from_dict_or_multidict(data, key, default=None):
    """Get a list from 'data'.

    If data is a MultiDict, then we use 'getlist' if the data is a plain dict,
    then we just use __getitem__.

    The rationale is that data POSTed as multipart/form-data gets parsed into a
    MultiDict, but data POSTed as application/json gets parsed into a plain
    dict(key:list).
    """
    getlist = getattr(data, 'getlist', None)
    if getlist is not None:
        return getlist(key, default)
    return data.get(key, default)


def get_overridden_query_dict(defaults, data):
    """Returns a QueryDict with the values of 'defaults' overridden by the
    values in 'data'.

    :param defaults: The dictionary containing the default values.
    :type defaults: dict
    :param data: The data used to override the defaults.
    :type data: :class:`django.http.QueryDict`
    :return: The updated QueryDict.
    :raises: :class:`django.http.QueryDict`
    """
    # Create a writable query dict.
    new_data = QueryDict('').copy()
    # Missing fields will be taken from the node's current values.  This
    # is to circumvent Django's ModelForm (form created from a model)
    # default behaviour that requires all the fields to be defined.
    new_data.update(defaults)
    # We can't use update here because data is a QueryDict and 'update'
    # does not replaces the old values with the new as one would expect.
    for k, v in data.items():
        new_data[k] = v
    return new_data


def extract_oauth_key_from_auth_header(auth_data):
    """Extract the oauth key from auth data in HTTP header.

    :param auth_data: {string} The HTTP Authorization header.

    :return: The oauth key from the header, or None.
    """
    for entry in auth_data.split():
        key_value = entry.split('=', 1)
        if len(key_value) == 2:
            key, value = key_value
            if key == 'oauth_token':
                return value.rstrip(',').strip('"')
    return None


def extract_oauth_key(request):
    """Extract the oauth key from a request's headers.

    Raises :class:`Unauthorized` if no key is found.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if auth_header is None:
        raise Unauthorized("No authorization header received.")
    key = extract_oauth_key_from_auth_header(auth_header)
    if key is None:
        raise Unauthorized("Did not find request's oauth token.")
    return key


def get_oauth_token(request):
    """Get the OAuth :class:`piston.models.Token` used for `request`.

    Raises :class:`Unauthorized` if no key is found, or if the token is
    unknown.
    """
    try:
        return Token.objects.get(key=extract_oauth_key(request))
    except Token.DoesNotExist:
        raise Unauthorized("Unknown OAuth token.")
