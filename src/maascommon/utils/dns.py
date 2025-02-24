#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import re

# Labels are at most 63 octets long, and a name can be many of them.
LABEL = r"[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}"
NAMESPEC = rf"({LABEL}[.])*{LABEL}[.]?"


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
        raise ValueError(
            "Hostname is too long.  Maximum allowed is 255 characters."
        )
    # A hostname consists of "labels" separated by dots.
    labels = name.split(".")
    for label in labels:
        if len(label) == 0:
            raise ValueError("DNS name contains an empty label.")
        if len(label) > 63:
            raise ValueError(
                "Label is too long: %r.  Maximum allowed is 63 characters."
                % label
            )
        if label.startswith("-") or label.endswith("-"):
            raise ValueError(
                "Label cannot start or end with hyphen: %r." % label
            )
        if not label_chars.match(label):
            raise ValueError(
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
        raise ValueError(
            "Hostname is too long.  Maximum allowed is 255 characters."
        )
    # A hostname consists of "labels" separated by dots.
    host_part = hostname.split(".")[0]
    if "_" in host_part:
        # The host label cannot contain underscores; the rest of the name can.
        raise ValueError(
            "Host label cannot contain underscore: %r." % host_part
        )
    validate_domain_name(hostname)
