# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL and DNS-related utilities."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import _lazy_re_compile, URLValidator


def validate_domain_name(name):
    """Validator for domain names.

    :param name: Input value for a domain name.  Must not include hostname.
    :raise ValidationError: If the domain name is not valid according to
    RFCs 952 and 1123.
    """
    # Valid characters within a hostname label: ASCII letters, ASCII digits,
    # hyphens.
    # Technically we could write all of this as a single regex, but it's not
    # very good for code maintenance.
    label_chars = re.compile("[a-zA-Z0-9-]*$")

    if len(name) > 255:
        raise ValidationError(
            "Hostname is too long.  Maximum allowed is 255 characters."
        )
    # A hostname consists of "labels" separated by dots.
    labels = name.split(".")
    for label in labels:
        if len(label) == 0:
            raise ValidationError("DNS name contains an empty label.")
        if len(label) > 63:
            raise ValidationError(
                "Label is too long: %r.  Maximum allowed is 63 characters."
                % label
            )
        if label.startswith("-") or label.endswith("-"):
            raise ValidationError(
                "Label cannot start or end with hyphen: %r." % label
            )
        if not label_chars.match(label):
            raise ValidationError(
                "Label contains disallowed characters: %r." % label
            )


def validate_hostname(hostname):
    """Validator for hostnames.

    :param hostname: Input value for a hostname.  May include domain.
    :raise ValidationError: If the hostname is not valid according to RFCs 952
        and 1123.
    """
    # Valid characters within a hostname label: ASCII letters, ASCII digits,
    # hyphens, and underscores.  Not all are always valid.
    # Technically we could write all of this as a single regex, but it's not
    # very good for code maintenance.

    if len(hostname) > 255:
        raise ValidationError(
            "Hostname is too long.  Maximum allowed is 255 characters."
        )
    # A hostname consists of "labels" separated by dots.
    host_part = hostname.split(".")[0]
    if "_" in host_part:
        # The host label cannot contain underscores; the rest of the name can.
        raise ValidationError(
            "Host label cannot contain underscore: %r." % host_part
        )
    validate_domain_name(hostname)


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
