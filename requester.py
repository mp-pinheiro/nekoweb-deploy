import logging
import time

import requests
from requests.exceptions import HTTPError, RequestException

logger = logging.getLogger("neko-deploy")

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

MAX_SLEEP = 60.0


class Requester:
    _shared_state = {}

    def __init__(self, max_retries=5, backoff_factor=1, exponential_backoff=False):
        self.__dict__ = self._shared_state
        if not hasattr(self, "max_retries"):
            self.max_retries = max_retries
        if not hasattr(self, "backoff_factor"):
            self.backoff_factor = backoff_factor
        if not hasattr(self, "exponential_backoff"):
            self.exponential_backoff = exponential_backoff

    @property
    def session(self):
        if not hasattr(self, "_session_obj"):
            self._session_obj = requests.Session()
        return self._session_obj

    def _backoff_wait(self, attempt):
        if self.exponential_backoff:
            return min(self.backoff_factor * (2 ** (attempt - 1)), MAX_SLEEP)
        return min(self.backoff_factor, MAX_SLEEP)

    def _retry_wait(self, response, attempt):
        if response is not None and response.status_code == 429:
            reset = response.headers.get("ratelimit-reset")
            if reset:
                try:
                    reset_ms = int(reset)
                except (TypeError, ValueError):
                    reset_ms = None
                if reset_ms is not None:
                    now_ms = int(time.time() * 1000)
                    if reset_ms > now_ms:
                        return min((reset_ms - now_ms) / 1000.0, MAX_SLEEP)
        return self._backoff_wait(attempt)

    def request(self, method, url, **kwargs):
        """Make a request to the given URL with the given method.

        Retries transient statuses (408/429/5xx) and network errors with backoff,
        honoring the NekoWeb ``ratelimit-reset`` header on 429 responses.

        Args:
            method (str): The HTTP method to use for the request.
            url (str): The URL to make the request to.
            ignored_errors (dict): Optional mapping of status codes to match rules; a
                matching response is returned instead of raising.
                {400: {"message": "File/folder already exists"}}
                {404: {"partial_message": "not exist"}}
                {404: {"ignore_all": True}}
            **kwargs: Additional keyword arguments passed to the session request.

        Returns:
            requests.Response: The response object for the request (any 2xx, or a
            response matching ``ignored_errors``).

        Raises:
            HTTPError: If the request fails after the maximum number of retries, or on
            a non-retryable status that is not ignored.
        """
        ignored_errors = kwargs.pop("ignored_errors", {})
        response = None

        for attempt in range(1, self.max_retries + 1):
            logger.debug(
                {
                    "message": "Making request",
                    "method": method,
                    "url": url,
                    "attempt": attempt,
                }
            )
            try:
                response = self.session.request(method, url, **kwargs)
            except RequestException as exc:
                logger.debug(
                    {
                        "message": "Network error, retrying",
                        "method": method,
                        "url": url,
                        "attempt": attempt,
                        "error": str(exc),
                    }
                )
                response = None
                if attempt < self.max_retries:
                    time.sleep(self._backoff_wait(attempt))
                    continue
                break

            if response.ok:
                return response

            if response.status_code in RETRYABLE_STATUS:
                wait = self._retry_wait(response, attempt)
                logger.debug(
                    {
                        "message": "Retryable status, backing off",
                        "method": method,
                        "url": url,
                        "status": response.status_code,
                        "ratelimit_remaining": response.headers.get("ratelimit-remaining"),
                        "attempt": attempt,
                        "wait": wait,
                    }
                )
                if attempt < self.max_retries:
                    time.sleep(wait)
                    continue
                break

            if self._is_ignored(response, ignored_errors):
                return response
            raise self._classify_error(response, method, url)

        if response is not None and self._is_ignored(response, ignored_errors):
            return response
        if response is not None:
            raise HTTPError(
                f"Max retries ({self.max_retries}) exceeded for {method} {url}; "
                f"last status {response.status_code}",
                response=response,
            )
        raise HTTPError(
            f"Max retries ({self.max_retries}) exceeded for {method} {url}; "
            f"last error: network exception"
        )

    @staticmethod
    def _is_ignored(response, ignored_errors):
        if response.status_code in ignored_errors:
            error = ignored_errors[response.status_code]
            partial = error.get("partial_message")
            return (
                bool(error.get("ignore_all"))
                or error.get("message") == response.text
                or (partial is not None and partial in response.text)
            )
        return False

    @staticmethod
    def _classify_error(response, method, url):
        status = response.status_code
        if status in (401, 403):
            msg = (
                f"Authentication or permission denied (status {status}) for {method} {url}. "
                "Verify API_KEY; for migrated sites set DEPLOY_DIR to your /<domain> folder."
            )
        elif status == 404:
            msg = f"Not found (status 404) for {method} {url}"
        elif 500 <= status < 600:
            msg = f"NekoWeb server error (status {status}) for {method} {url}"
        else:
            msg = f"HTTP error (status {status}) for {method} {url}"
        return HTTPError(msg, response=response)
