from urllib.parse import quote, urlparse

import pytest

from camoufox_cli.identity import _proxy_url_with_auth


class TestProxyUrlWithAuth:
    def test_no_auth_returns_server_unchanged(self):
        assert _proxy_url_with_auth("http://host:8080") == "http://host:8080"

    @pytest.mark.parametrize(
        ("username", "password"),
        [
            ("user", "p@ss"),
            ("user", "pa/ss"),
            ("u@s:er", "p:w@x/y"),
        ],
    )
    def test_special_chars_round_trip(self, username, password):
        proxy_url = (
            f"http://{quote(username, safe='')}:{quote(password, safe='')}@127.0.0.1:8080"
        )
        rebuilt = _proxy_url_with_auth(proxy_url)
        parsed = urlparse(rebuilt)
        assert parsed.hostname == "127.0.0.1"
        assert parsed.port == 8080
        assert parsed.username == quote(username, safe="")
        assert parsed.password == quote(password, safe="")
