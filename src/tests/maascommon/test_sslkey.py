#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from OpenSSL import crypto

from maascommon.sslkey import find_ssl_common_name, get_html_display_for_key
from maasserver.testing import get_data


class TestGetHTMLDisplayForKey:
    def test_display_returns_only_md5(self, mocker):
        key_string = get_data("data/test_x509_0.pem")
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, key_string)
        subject = cert.get_subject()
        cn = find_ssl_common_name(subject)
        mocker.patch(
            "maascommon.sslkey", find_ssl_common_name
        ).return_value = None
        display = get_html_display_for_key(key_string)
        assert cn in display

    def test_display_returns_cn_and_md5(self):
        key_string = get_data("data/test_x509_0.pem")
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, key_string)
        subject = cert.get_subject()
        cn = find_ssl_common_name(subject)
        display = get_html_display_for_key(key_string)
        assert cn in display

    def test_decode_md5_as_ascii(self):
        # the key MD5 is correctly printed (and not repr'd)
        key_string = get_data("data/test_x509_0.pem")
        display = get_html_display_for_key(key_string)
        assert "b\\'" not in display
