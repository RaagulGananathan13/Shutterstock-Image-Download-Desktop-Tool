"""
shutterstock_api.py — Thin client for the Shutterstock REST API v2.

Implements:
  - search_images()       — GET /v2/images/search
  - get_subscription_id() — GET /v2/user/subscriptions (cached per session)
  - license_image()       — POST /v2/images/licenses

All methods raise typed exceptions that the GUI layer catches to show
friendly, non-crashing messages.
"""

import requests

BASE_URL = "https://api.shutterstock.com/v2"

# ---------------------------------------------------------------------------
# Custom exception hierarchy
# ---------------------------------------------------------------------------


class ShutterstockAPIError(Exception):
    """Base exception for all Shutterstock API errors."""
    pass


class AuthError(ShutterstockAPIError):
    """401 — bad or expired token."""
    def __init__(self, message="Invalid or expired API token. Please check your key in Settings."):
        super().__init__(message)


class SubscriptionError(ShutterstockAPIError):
    """403 — token lacks the required scope/subscription for this action."""
    def __init__(self, message="This API key does not have an active licensing subscription. "
                               "Search still works but full-resolution download is not available on this plan."):
        super().__init__(message)


class RateLimitError(ShutterstockAPIError):
    """429 — too many requests."""
    def __init__(self, message="Too many requests, please wait a moment and try again."):
        super().__init__(message)


class NetworkError(ShutterstockAPIError):
    """Network / timeout / connection error."""
    def __init__(self, message="Network error: could not reach Shutterstock. Check your internet connection."):
        super().__init__(message)


# ---------------------------------------------------------------------------
# API client class
# ---------------------------------------------------------------------------

class ShutterstockAPI:
    """Stateful API client. Holds the bearer token and caches the subscription ID."""

    def __init__(self, api_token: str):
        self._token = api_token
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        })
        self._subscription_id: str | None = None  # cached after first fetch

    def update_token(self, new_token: str) -> None:
        """Update the bearer token (e.g. user changed it in Settings) and clear cached state."""
        self._token = new_token
        self._session.headers["Authorization"] = f"Bearer {new_token}"
        self._subscription_id = None  # force re-fetch

    # ---- helpers -----------------------------------------------------------

    def _handle_response_errors(self, resp: requests.Response) -> None:
        """Raise the appropriate typed exception for non-2xx status codes."""
        if resp.status_code == 401:
            raise AuthError()
        if resp.status_code == 403:
            raise SubscriptionError()
        if resp.status_code == 429:
            raise RateLimitError()
        if not resp.ok:
            # Generic server/client error — surface the status code
            raise ShutterstockAPIError(
                f"Shutterstock API error {resp.status_code}: {resp.text[:300]}"
            )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Perform an HTTP request with automatic error mapping."""
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

    # ---- public API --------------------------------------------------------

    def search_images(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
        sort: str | None = None,
        image_type: str | None = None,
    ) -> dict:
        """
        Search for images.

        Returns the raw JSON dict from the API, which includes:
          - page, per_page, total_count
          - data: list of image objects with 'id', 'description', 'assets'
        """
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
        """
        Fetch the user's first active subscription ID.
        Cached in memory for the session — only hits the API once.

        Raises SubscriptionError if no active subscription is found.
        """
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
        # Take the first active subscription
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
        """
        License an image and return the signed download URL.

        Tries `size`; if the API rejects it, falls back to 'large'.
        Returns the download URL string.
        """
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
                # Retry with smaller size
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
            # Try nested download object
            download_obj = image_info.get("download", {})
            download_url = download_obj.get("url")
        if not download_url:
            # Some responses nest it under assets
            assets = image_info.get("assets", {})
            if assets:
                download_url = assets.get("huge", {}).get("url") or assets.get("large", {}).get("url")
        if not download_url:
            raise ShutterstockAPIError(
                "Could not extract download URL from the license response. "
                "The image may not be available for download with this subscription."
            )
        return download_url
