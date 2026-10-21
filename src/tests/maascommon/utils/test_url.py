#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
import pytest

from maascommon.utils.url import validate_url

EXTENDED_SCHEMES = ["http", "https", "ftp", "ftps", "git", "file", "git+ssh"]


class TestValidateURL:
    @pytest.mark.parametrize(
        "url",
        [
            "http://foo",
            "http://foo/",
            "http://foo/bar",
            "http://foo/bar/",
            "http://localhost",
            "http://maas.example.com",
            "http://maas.example.com.",
            "http://xn--bcher-kva.example",
            "http://bücher.example",
            "http://10.0.0.1",
            "http://10.0.0.1:5240/MAAS/?q=1#top",
            "http://example.com:5",
            "http://foo:0",
            "http://foo:65535",
            "http://[::1]",
            "http://[2001:db8::1]:5240/MAAS",
            "http://[::ffff:10.0.0.1]",
            "http://user:password@maas.example.com",
            "HTTPS://MAAS.EXAMPLE.COM",
        ],
    )
    def test_accepts(self, url: str) -> None:
        validate_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "file://localhost/path",
            "git://example.com/",
            "git+ssh://git@github.com/example/hg-git.git",
        ],
    )
    def test_accepts_extended_schemes(self, url: str) -> None:
        validate_url(url, schemes=EXTENDED_SCHEMES)

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "foo",
            "://foo",
            "http://",
            "http://bad!host",
            "http://-foo",
            "http://foo-",
            "http://foo.123",
            "http://256.0.0.1",
            "http://01.0.0.1",
            "http://[::g]",
            "http://[1:2:3]",
            "http://foo bar",
            "http://foo/\tbar",
            "http://foo/bar\n",
            "http://www.djangoproject.com/\n",
            "http://[::ffff:192.9.5.5]\n",
            "http://www.asdasdasdasdsadfm.com.br ",
            "http://www.asdasdasdasdsadfm.com.br z",
            "http://foo,http://bar",
            "http://foo:65536",
            "http://10.0.0.1:99999/MAAS",
            "http://[::1]:65536",
            "http://" + "a" * 64 + ".com",
            "http://" + ".".join(["abcdefghi"] * 26) + ".com",
            "http://example.com/" + "x" * 2048,
        ],
    )
    def test_rejects(self, url: str) -> None:
        with pytest.raises(ValueError):
            validate_url(url)

    def test_rejects_hostname_starting_with_hyphen_with_extended_schemes(
        self,
    ) -> None:
        with pytest.raises(ValueError):
            validate_url("git://-invalid.com", schemes=EXTENDED_SCHEMES)

    def test_rejects_non_string(self) -> None:
        with pytest.raises(ValueError):
            validate_url(1234)  # pyright: ignore[reportArgumentType]

    def test_defaults_to_http_and_https(self) -> None:
        validate_url("https://maas.example.com")
        with pytest.raises(ValueError):
            validate_url("ftp://maas.example.com")

    def test_accepts_given_schemes(self) -> None:
        validate_url("icmp://10.0.0.1", schemes=["icmp"])
        with pytest.raises(ValueError):
            validate_url("http://10.0.0.1", schemes=["icmp"])
