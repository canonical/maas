# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL and DNS-related utilities."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import _lazy_re_compile, URLValidator

from maascommon.utils.dns import (
    validate_domain_name as maas_common_validate_domain_name,
)
from maascommon.utils.dns import (
    validate_hostname as maas_common_validate_hostname,
)


def validate_domain_name(name):
    # This function has been moved to maascommon. Still, we keep it here because maasserver expects it to return a django
    # ValidationError.
    try:
        return maas_common_validate_domain_name(name)
    except ValueError as e:
        raise ValidationError(str(e)) from e


def validate_hostname(hostname):
    # This function has been moved to maascommon. Still, we keep it here because maasserver expects it to return a django
    # ValidationError.
    try:
        return maas_common_validate_hostname(hostname)
    except ValueError as e:
        raise ValidationError(str(e)) from e


def validate_url(url, schemes=("http", "https")):
    """Validator for URLs.

    Uses's django's URLValidator plumbing but isn't as restrictive and
    URLs of the form http://foo are considered valid.

    Built from:

    `https://docs.djangoproject.com/en/2.1/_modules/django/
        core/validators/#URLValidator`

    :param url: Input value for a url.
    :raise ValidationError: If the url is not valid.
    """
    # Re-structure django's host regex to allow for hostnames without domain
    host_re = (
        "("
        + URLValidator.hostname_re
        + URLValidator.domain_re
        + URLValidator.tld_re
        + "|"
        + URLValidator.hostname_re
        + "|localhost)"
    )

    # override builtin regexp to change host and port bits
    regex = _lazy_re_compile(
        r"^(?:[a-z0-9.+-]*)://"
        r"(?:[^\s:@/]+(?::[^\s:@/]*)?@)?"
        r"(?:"
        + URLValidator.ipv4_re
        + "|"
        + URLValidator.ipv6_re
        + "|"
        + host_re
        + ")"
        r"(?::\d{1,5})?"
        r"(?:[/?#][^\s]*)?"
        r"\Z",
        re.IGNORECASE,
    )
    validator = URLValidator(regex=regex, schemes=schemes)
    return validator(url)
