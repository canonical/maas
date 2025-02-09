# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for Piston-based MAAS APIs."""

__all__ = [
    "extract_bool",
    "extract_oauth_key",
    "get_list_from_dict_or_multidict",
    "get_mandatory_param",
    "get_oauth_token",
    "get_optional_list",
    "get_optional_param",
    "get_overridden_query_dict",
]

from django.http import QueryDict
from formencode.validators import Invalid
from piston3.models import Token

from maasserver.config_forms import DictCharField
from maasserver.exceptions import MAASAPIValidationError, Unauthorized


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
    assert isinstance(value, str)
    if value == "0":
        return False
    elif value == "1":
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
        raise MAASAPIValidationError("No provided %s!" % key)
    if validator is not None:
        try:
            return validator.to_python(value)
        except Invalid as e:
            raise MAASAPIValidationError(f"Invalid {key}: {e.msg}")  # noqa: B904
    else:
        return value


def _validate_param(key, value, validator):
    """Validates the spcified `value` using the supplied `validator`."""
    try:
        return validator.to_python(value)
    except Invalid as e:
        raise MAASAPIValidationError(f"Invalid {key}: {e.msg}")  # noqa: B904


def get_optional_param(data, key, default=None, validator=None):
    """Get the optional parameter from the provided data dict if exists.
    If it exists it validates if validator given.

    :param data: The data dict (usually request.data or request.GET where
        request is a django.http.HttpRequest).
    :param data: dict
    :param key: The parameter's key.
    :type key: unicode
    :param default: The default value, if not present.
    :type default: object
    :param validator: An optional validator that will be used to validate the
         retrieved value.
    :type validator: formencode.validators.Validator
    :return: The value of the parameter.
    :raises: ValidationError
    """
    value = data.get(key)
    if value is None:
        return default
    if validator is not None:
        value = _validate_param(key, value, validator)
    return value


def get_optional_list(data, key, default=None, validator=None):
    """Get the list from the provided data dict or return a default value.

    Optionally uses the specified `validator`.
    """
    values = data.getlist(key)
    if values == []:
        return default
    else:
        if validator is not None:
            for count, value in enumerate(values):
                values[count] = _validate_param(key, value, validator)
        return values


def get_list_from_dict_or_multidict(data, key, default=None):
    """Get a list from 'data'.

    If data is a MultiDict, then we use 'getlist' if the data is a plain dict,
    then we just use __getitem__.

    The rationale is that data POSTed as multipart/form-data gets parsed into a
    MultiDict, but data POSTed as application/json gets parsed into a plain
    dict(key:list).
    """
    getlist = getattr(data, "getlist", None)
    if getlist is not None:
        return getlist(key, default)
    return data.get(key, default)


def listify(value):
    """Return a list with `value` in it unless `value` is already a list."""
    if isinstance(value, list):
        return value
    return [value]


def get_overridden_query_dict(defaults, data, fields):
    """Returns a QueryDict with the values of 'defaults' overridden by the
    values in 'data'.

    :param defaults: The dictionary containing the default values.
    :type defaults: dict
    :param data: The data used to override the defaults.
    :type data: :class:`django.http.QueryDict` or dict
    :param fields: The list of field names to consider.
    :type fields: :class:`collections.Container`
    :return: The updated QueryDict.
    :raises: :class:`django.http.QueryDict`
    """
    new_data = QueryDict(mutable=True)
    # If the fields are a dict of django Fields see if one is a DictCharField.
    # DictCharField must have their values prefixed with the DictField name in
    # the returned data or defaults don't get carried.
    if isinstance(fields, dict):
        acceptable_fields = []
        for field_name, field in fields.items():
            acceptable_fields.append(field_name)
            if isinstance(field, DictCharField):
                for sub_field in field.names:
                    acceptable_fields.append(f"{field_name}_{sub_field}")
    else:
        acceptable_fields = fields
    # Missing fields will be taken from the node's current values.  This
    # is to circumvent Django's ModelForm (form created from a model)
    # default behaviour that requires all the fields to be defined.
    for k, v in defaults.items():
        if k in acceptable_fields:
            new_data.setlist(k, listify(v))
    # We can't use update here because data is a QueryDict and 'update'
    # does not replaces the old values with the new as one would expect.
    elements = data.lists() if isinstance(data, QueryDict) else data.items()
    for k, v in elements:
        new_data.setlist(k, listify(v))

    return new_data


def extract_oauth_key_from_auth_header(auth_data):
    """Extract the oauth key from auth data in HTTP header.

    :param auth_data: {string} The HTTP Authorization header.

    :return: The oauth key from the header, or None.
    """
    # Values only separated by commas (no whitespace).
    if len(auth_data.split()) == 2:
        for entry in auth_data.split()[1].split(","):
            key_value = entry.split("=", 1)
            if len(key_value) == 2:
                key, value = key_value
                if key == "oauth_token":
                    return value.strip('"')
    else:
        for entry in auth_data.split():
            key_value = entry.split("=", 1)
            if len(key_value) == 2:
                key, value = key_value
                if key == "oauth_token":
                    return value.rstrip(",").strip('"')
    return None


def extract_oauth_key(request):
    """Extract the oauth key from a request's headers.

    Raises :class:`Unauthorized` if no key is found.
    """
    auth_header = request.headers.get("authorization")
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
        raise Unauthorized("Unknown OAuth token.")  # noqa: B904
