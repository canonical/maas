# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom matchers for testing in the region."""

__all__ = [
    'HasStatusCode',
]

from testtools.content import (
    Content,
    UTF8_TEXT,
)
from testtools.matchers import (
    Matcher,
    Mismatch,
)


class HasStatusCode(Matcher):
    """Match if the given response has the expected HTTP status.

    In case of a mismatch this assumes that the response contains a textual
    body. If it's not already encoded as UTF-8, it is recoded, replacing any
    problematic characters in the process, like surrogate escapes.

    The response against which this matches is expected to be an instance of
    Django's `HttpResponse` though this is not explicitly tested.
    """

    def __init__(self, status_code):
        super(HasStatusCode, self).__init__()
        self.status_code = status_code

    def match(self, response):
        if response.status_code != self.status_code:
            response_dump = response.serialize()
            if response.charset.lower() not in {"utf-8", "utf_8", "utf8"}:
                response_dump = response_dump.decode(response.charset)
                response_dump = response_dump.encode("utf-8", "replace")

            description = "Expected HTTP %s, got %s" % (
                self.status_code, response.status_code)
            details = {
                "Unexpected HTTP response": Content(
                    UTF8_TEXT, lambda: [response_dump]),
            }

            return Mismatch(description, details)
