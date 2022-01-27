# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom matchers for testing in the region."""


from http import HTTPStatus

from testtools.content import Content, UTF8_TEXT
from testtools.matchers import Matcher, MatchesSetwise, Mismatch


def describe_http_status(code):
    """Return a string describing the given HTTP status code."""
    try:
        code = HTTPStatus(code)
    except ValueError:
        return f"HTTP {code}"
    else:
        return "HTTP {code.value:d} {code.name}".format(code=code)


class HasStatusCode(Matcher):
    """Match if the given response has the expected HTTP status.

    In case of a mismatch this assumes that the response contains a textual
    body. If it's not already encoded as UTF-8, it is recoded, replacing any
    problematic characters in the process, like surrogate escapes.

    The response against which this matches is expected to be an instance of
    Django's `HttpResponse` though this is not explicitly tested.
    """

    def __init__(self, status_code):
        super().__init__()
        self.status_code = status_code

    def match(self, response):
        if response.status_code != self.status_code:
            response_dump = response.serialize()
            if response.charset.lower() not in {"utf-8", "utf_8", "utf8"}:
                response_dump = response_dump.decode(response.charset)
                response_dump = response_dump.encode("utf-8", "replace")

            description = "Expected {}, got {}".format(
                describe_http_status(self.status_code),
                describe_http_status(response.status_code),
            )
            details = {
                "Unexpected HTTP response": Content(
                    UTF8_TEXT, lambda: [response_dump]
                )
            }

            return Mismatch(description, details)


class MatchesSetwiseWithAll(MatchesSetwise):
    """Match `observed` using `MatchesSetwise` calling `all()` before the
    matching. This is useful when a matching needs to be performed
    on a related manager on an objects.

    machine = Machine(...)
    self.assertThat(
        machine,
        MatchesStructure(
            interfaces=MatchesSetwiseWithAll(
                MatchesStructure(mac_address=Equals(mac_address)))))
    """

    def match(self, observed):
        return super().match(observed.all())
