# wrapper for the shutterstock api.
# watch out for rate limits here, they are pretty strict
import requests
BASE_URL = "https://api.shutterstock.com/v2"
class ShutterstockAPIError(Exception):
    pass
class AuthError(ShutterstockAPIError):
    def __init__(self, message="Invalid or expired API token. Please check your key in Settings."):
        super().__init__(message)
class SubscriptionError(ShutterstockAPIError):
    def __init__(self, message="This API key does not have an active licensing subscription. "
                               "Search still works but full-resolution download is not available on this plan."):
        super().__init__(message)
class RateLimitError(ShutterstockAPIError):
    def __init__(self, message="Too many requests, please wait a moment and try again."):
        super().__init__(message)
class NetworkError(ShutterstockAPIError):
    def __init__(self, message="Network error: could not reach Shutterstock. Check your internet connection."):
        super().__init__(message)
class ShutterstockAPI:
    def __init__(self, api_token: str):
        self._token = api_token
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        })
        self._subscription_id: str | None = None  
    def update_token(self, new_token: str) -> None:
        self._token = new_token
        self._session.headers["Authorization"] = f"Bearer {new_token}"
        self._subscription_id = None  
    def _handle_response_errors(self, resp: requests.Response) -> None:
        if resp.status_code == 401:
            raise AuthError()
        if resp.status_code == 403:
            raise SubscriptionError()
        if resp.status_code == 429:
            raise RateLimitError()
        if not resp.ok:
            raise ShutterstockAPIError(
                f"Shutterstock API error {resp.status_code}: {resp.text[:300]}"
            )
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{BASE_URL}{path}"
        try:
            resp = self._session.request(method, url, timeout=30, **kwargs)
        except requests.exceptions.ConnectionError:
            raise NetworkError()
        except requests.exceptions.Timeout:
            raise NetworkError("Request timed out. Please try again.")
        except requests.exceptions.RequestException as exc:
            raise NetworkError(f"Network error: {exc}")
        self._handle_response_errors(resp)
        return resp
    def search_images(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
        sort: str | None = None,
        image_type: str | None = None,
    ) -> dict:
        params: dict = {
            "query": query,
            "page": page,
            "per_page": per_page,
        }
        if sort:
            params["sort"] = sort
        if image_type:
            params["image_type"] = image_type
        resp = self._request("GET", "/images/search", params=params)
        return resp.json()
    def get_subscription_id(self) -> str:
        if self._subscription_id:
            return self._subscription_id
        resp = self._request("GET", "/user/subscriptions")
        data = resp.json()
        subscriptions = data.get("data", [])
        if not subscriptions:
            raise SubscriptionError(
                "No active Shutterstock subscription found for this API key. "
                "Full-resolution download requires a paid licensing subscription."
            )
        self._subscription_id = subscriptions[0].get("id", "")
        if not self._subscription_id:
            raise SubscriptionError(
                "Subscription data is incomplete. Please check your Shutterstock account."
            )
        return self._subscription_id
    def license_image(
        self,
        image_id: str,
        subscription_id: str,
        size: str = "huge",
    ) -> str:
        payload = {
            "images": [
                {
                    "image_id": image_id,
                    "subscription_id": subscription_id,
                    "size": size,
                }
            ]
        }
        try:
            resp = self._request("POST", "/images/licenses", json=payload)
        except ShutterstockAPIError:
            if size != "large":
                payload["images"][0]["size"] = "large"
                resp = self._request("POST", "/images/licenses", json=payload)
            else:
                raise
        result = resp.json()
        images_data = result.get("data", [])
        if not images_data:
            raise ShutterstockAPIError("License response contained no image data.")
        image_info = images_data[0]
        download_url = image_info.get("url")
        if not download_url:
            download_obj = image_info.get("download", {})
            download_url = download_obj.get("url")
        if not download_url:
            assets = image_info.get("assets", {})
            if assets:
                download_url = assets.get("huge", {}).get("url") or assets.get("large", {}).get("url")
        if not download_url:
            raise ShutterstockAPIError(
                "Could not extract download URL from the license response. "
                "The image may not be available for download with this subscription."
            )
        return download_url
    def get_suggestions(self, query: str, limit: int = 10) -> list[str]:
        if not query or len(query) < 2:
            return []
        try:
            resp = self._request("GET", "/images/search/suggestions", params={"query": query})
            data = resp.json()
            suggestions = data.get("data", [])
            if suggestions and isinstance(suggestions[0], str):
                return suggestions[:limit]
            if suggestions and isinstance(suggestions[0], dict):
                return [s.get("text", s.get("keyword", "")) for s in suggestions[:limit] if s]
            return []
        except Exception:
            return []