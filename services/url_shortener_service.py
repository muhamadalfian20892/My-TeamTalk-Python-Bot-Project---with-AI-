import logging
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

class URLShortenerService:
    """A service to shorten URLs using the TinyURL API."""
    def __init__(self):
        self._enabled = REQUESTS_AVAILABLE
        self.api_url = "http://tinyurl.com/api-create.php"
        if not self._enabled:
            logging.warning("URL Shortener disabled: 'requests' library not found.")

    def is_enabled(self) -> bool:
        """Check if the service is enabled."""
        return self._enabled

    def shorten_url(self, long_url: str) -> str:
        """
        Shortens a given URL.

        Args:
            long_url: The URL to shorten.

        Returns:
            A string containing the shortened URL or an error message.
        """
        if not self.is_enabled():
            return "[Bot] URL shortener is disabled ('requests' library not installed)."
        if not long_url.startswith(('http://', 'https://')):
            return "[Bot Error] Invalid URL. Please provide a full URL starting with http:// or https://"
        
        try:
            response = requests.get(self.api_url, params={'url': long_url}, timeout=10)
            response.raise_for_status()
            if response.text == "Error":
                return "[Bot Error] The TinyURL API returned an error. The URL may be invalid or blacklisted."
            return f"Shortened URL: {response.text}"
        except requests.exceptions.Timeout:
            return f"[Bot Error] Request timed out while shortening URL."
        except requests.exceptions.RequestException as e:
            logging.error(f"Error shortening URL {long_url}: {e}")
            return f"[Bot Error] Could not shorten URL. The service might be down or the URL is invalid."