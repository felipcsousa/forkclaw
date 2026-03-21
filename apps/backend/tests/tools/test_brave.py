import pytest
from unittest.mock import MagicMock, patch

from app.tools.web.providers.brave import BraveWebSearchProvider
from app.tools.web.providers.base import SearchProviderResponse, SearchResultItem
import httpx

def test_brave_web_search_provider():
    with patch.dict("os.environ", {"BRAVE_API_KEY": "test_key"}), \
         patch("httpx.Client") as mock_client_class:

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Test Title", "url": "https://test.com", "description": "Test snippet"},
                    {"title": "Missing Snippet", "url": "https://missing.com"},
                    "not a dict",
                    {"title": "", "url": "https://empty.com"}, # should be skipped
                    {"url": "https://notitle.com"}, # should be skipped
                ]
            }
        }
        mock_client.get.return_value = mock_response

        provider = BraveWebSearchProvider(timeout_seconds=5.0)

        # Test default initialization
        assert provider.api_key == "test_key"
        assert provider.timeout_seconds == 5.0

        result = provider.search("test query", 2)

        assert isinstance(result, SearchProviderResponse)
        assert result.provider == "brave"
        assert result.query == "test query"
        assert len(result.results) == 2

        assert result.results[0].title == "Test Title"
        assert result.results[0].url == "https://test.com"
        assert result.results[0].snippet == "Test snippet"

        assert result.results[1].title == "Missing Snippet"
        assert result.results[1].snippet == ""

        mock_client.get.assert_called_once_with(
            "https://api.search.brave.com/res/v1/web/search",
            params={
                "q": "test query",
                "count": 2,
                "text_decorations": "0",
                "result_filter": "web",
            },
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": "test_key",
            }
        )

def test_brave_web_search_provider_missing_key():
    with patch.dict("os.environ", clear=True):
        with pytest.raises(ValueError, match="BRAVE_API_KEY is required to use web_search."):
            BraveWebSearchProvider()

def test_brave_web_search_provider_empty_results():
    with patch.dict("os.environ", {"BRAVE_API_KEY": "test_key"}), \
         patch("httpx.Client") as mock_client_class:

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {} # Empty payload
        mock_client.get.return_value = mock_response

        provider = BraveWebSearchProvider()
        result = provider.search("test query", 5)

        assert len(result.results) == 0
