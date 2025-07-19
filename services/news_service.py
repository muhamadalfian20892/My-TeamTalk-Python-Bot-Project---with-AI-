import logging
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

class NewsService:
    def __init__(self, api_key):
        self.api_key = api_key
        # Using NewsAPI.org. Users can get a free key from https://newsapi.org
        self.base_url = "https://newsapi.org/v2/top-headlines?"
        self._enabled = REQUESTS_AVAILABLE and bool(self.api_key)
        if not self._enabled:
            logging.warning("News feature is disabled (check News API key or 'requests' library).")

    def is_enabled(self):
        return self._enabled

    def get_news(self, topic: str = None, country: str = 'us', page_size: int = 5) -> str:
        if not self.is_enabled():
            return "[Bot] News feature is disabled (check News API key in config.json)."

        params = {
            'apiKey': self.api_key,
            'pageSize': page_size
        }
        # If a topic is provided (and it's not 'top'), search for that query.
        # Otherwise, get top headlines for the specified country.
        if topic and topic.lower() != 'top':
            params['q'] = topic
            search_term = topic
        else:
            params['country'] = country
            search_term = "Top Stories"

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                return f"[News Error] API Error: {data.get('message', 'Unknown API error')}."

            articles = data.get("articles", [])
            if not articles:
                return f"No news articles found for '{search_term}'. Try a different topic."

            headlines = [f"--- Top {len(articles)} Headlines for '{search_term}' ---"]
            for i, article in enumerate(articles):
                title = article.get('title', 'No Title')
                source = article.get('source', {}).get('name', 'Unknown Source')
                headlines.append(f"{i+1}. {title} ({source})")
            
            return "\n".join(headlines)

        except requests.exceptions.Timeout:
            return "[News Error] The request to the news service timed out."
        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 401:
                 return "[News Error] Unauthorized. Your News API key may be invalid."
             if e.response.status_code == 429:
                 return "[News Error] Too many requests. You have been rate-limited by the news service."
             return f"[News Error] Could not fetch news. HTTP Error: {e.response.status_code}"
        except requests.exceptions.RequestException:
            return "[News Error] Could not fetch news. Check your internet connection."
        except Exception as e:
            logging.error(f"Unexpected news error: {e}", exc_info=True)
            return "[News Error] An unexpected error occurred while fetching news."