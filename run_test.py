import pytest

from app.tools.web.fetch import fetch_web_document
from unittest.mock import patch
import respx
import httpx

@respx.mock
def test_mocking():
    respx.get("http://example.com/foo").mock(return_value=httpx.Response(200, text="hello"))
    with patch("app.tools.web.fetch.socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [(0, 0, 0, "", ("8.8.8.8", 80))]
        result = fetch_web_document(url="http://example.com/foo", extract_mode="text", max_chars=100, timeout_seconds=10.0, max_response_bytes=1000)
        print(result)

if __name__ == "__main__":
    test_mocking()
